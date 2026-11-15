// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

using DemoAgent;
using DemoAgent.Agent;
using Agent365.Samples.Observability;
using Azure;
using Azure.AI.OpenAI;
using Microsoft.Agents.A365.Tooling.Extensions.AgentFramework.Services;
using Microsoft.Agents.A365.Tooling.Services;
using Microsoft.Agents.Builder;
using Microsoft.Agents.Core;
using Microsoft.Agents.Hosting.AspNetCore;
using Microsoft.Agents.Storage;
using Microsoft.Agents.Storage.Transcript;
using Microsoft.Extensions.AI;
using Microsoft.OpenTelemetry;
using System.Reflection;



var builder = WebApplication.CreateBuilder(args);
builder.Configuration.AddUserSecrets(Assembly.GetExecutingAssembly());
// One observability token provider per agent instance (all instances of the blueprint).
using var observabilityTokens = MultiInstanceObservabilityTokenResolver.CreateIfEnabled(builder.Configuration);
var agent365ExporterEnabled = observabilityTokens is not null;

// Configure OpenTelemetry distro — Console exporter only in Development to avoid PII leaks
builder.UseMicrosoftOpenTelemetry(o =>
{
    o.Exporters = agent365ExporterEnabled ? ExportTarget.Agent365 : (ExportTarget)0;
    if (builder.Environment.IsDevelopment())
    {
        o.Exporters |= ExportTarget.Console;
    }

    if (observabilityTokens is not null)
    {
        o.Agent365.Exporter.UseS2SEndpoint = true;
        o.Agent365.Exporter.TokenResolver = observabilityTokens.ResolveAsync;
    }

    // Agent365-only export suppresses infrastructure instrumentation by default.
    // Re-enable explicitly so HTTP calls (Azure OpenAI, auth, Teams) appear in traces.
    o.Instrumentation.EnableAspNetCoreInstrumentation = true;
    o.Instrumentation.EnableHttpClientInstrumentation = true;
    o.Instrumentation.EnableAzureSdkInstrumentation = true;
});

builder.Services.AddControllers();
builder.Services.AddHttpClient("WebClient", client => client.Timeout = TimeSpan.FromSeconds(600));

// Optional diagnostics: log grant_type/scope of failed token requests (no secrets).
if (builder.Configuration.GetValue<bool>("Diagnostics:LogTokenScopes"))
{
    builder.Services.AddTransient<DemoAgent.Diagnostics.TokenScopeLoggingHandler>();
    builder.Services.AddHttpClient("MSALClientFactory").AddHttpMessageHandler<DemoAgent.Diagnostics.TokenScopeLoggingHandler>();
}
builder.Services.AddHttpContextAccessor();
builder.Logging.AddConsole();

// **********  Configure A365 Services **********
// Add A365 Tooling Server integration
builder.Services.AddSingleton<IMcpToolRegistrationService, McpToolRegistrationService>();
builder.Services.AddSingleton<IMcpToolServerConfigurationService, McpToolServerConfigurationService>();
// **********  END Configure A365 Services **********

// Add AspNet token validation
builder.Services.AddAgentAspNetAuthentication(builder.Configuration);

// Register IStorage.  For development, MemoryStorage is suitable.
// For production Agents, persisted storage should be used so
// that state survives Agent restarts, and operate correctly
// in a cluster of Agent instances.
builder.Services.AddSingleton<IStorage, MemoryStorage>();

// Add AgentApplicationOptions from config.
builder.AddAgentApplicationOptions();

// Add the bot (which is transient)
builder.AddAgent<MyAgent>();

// Register IChatClient with correct types
builder.Services.AddSingleton<IChatClient>(sp => {

    var confSvc = sp.GetRequiredService<IConfiguration>();
    var endpoint = confSvc["AIServices:AzureOpenAI:Endpoint"] ?? string.Empty;
    var deployment = confSvc["AIServices:AzureOpenAI:DeploymentName"] ?? string.Empty;
    // Optional: client ID of the user-assigned managed identity (App Service). Empty locally → az login.
    var managedIdentityClientId = confSvc["AIServices:AzureOpenAI:ManagedIdentityClientId"];

    AssertionHelpers.ThrowIfNullOrEmpty(endpoint, "AIServices:AzureOpenAI:Endpoint configuration is missing and required.");
    AssertionHelpers.ThrowIfNullOrEmpty(deployment, "AIServices:AzureOpenAI:DeploymentName configuration is missing and required.");

    // Keyless auth: managed identity in Azure, developer credentials (az login) locally.
    var credential = new Azure.Identity.DefaultAzureCredential(new Azure.Identity.DefaultAzureCredentialOptions
    {
        ManagedIdentityClientId = string.IsNullOrEmpty(managedIdentityClientId) ? null : managedIdentityClientId,
        TenantId = confSvc["AIServices:AzureOpenAI:TenantId"]
    });

    return new AzureOpenAIClient(new Uri(endpoint), credential)
        .GetChatClient(deployment)
        .AsIChatClient()
        .AsBuilder()
        .UseFunctionInvocation()
        .UseOpenTelemetry(sourceName: null, configure: (cfg) => cfg.EnableSensitiveData = true)
        .Build(); 
});

// Transcript logging is intentionally disabled: it writes full conversations (incl. email content)
// to local disk, and it cannot deserialize the A365 EmailResponse entity (the exception text was
// then sent back to the user as a second email).
// builder.Services.AddSingleton<Microsoft.Agents.Builder.IMiddleware[]>([new TranscriptLoggerMiddleware(new FileTranscriptLogger())]);

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseDeveloperExceptionPage();
}

app.UseRouting();
app.UseAuthentication();
app.UseAuthorization();


// Map the /api/messages endpoint to the AgentApplication
var messagesRoute = app.MapPost("/api/messages", async (HttpRequest request, HttpResponse response, IAgentHttpAdapter adapter, IAgent agent, CancellationToken cancellationToken) =>
{
    await adapter.ProcessAsync(request, response, agent, cancellationToken);
});

// Outside local testing, only accept JWT-authenticated calls from the Agent 365 / Bot channels.
if (!app.Environment.IsDevelopment() && app.Environment.EnvironmentName != "Playground")
{
    messagesRoute.RequireAuthorization();
}

// Health check endpoint for CI/CD pipelines and monitoring
app.MapGet("/api/health", () => Results.Ok(new { status = "healthy", timestamp = System.DateTime.UtcNow }));

if (app.Environment.IsDevelopment() || app.Environment.EnvironmentName == "Playground")
{
    app.MapGet("/", () => "Ava – Agent 365 demo agent");
    app.UseDeveloperExceptionPage();
    app.MapControllers().AllowAnonymous();

    // Hard coded for brevity and ease of testing. 
    // In production, this should be set in configuration.
    app.Urls.Add($"http://localhost:3978");
}
else
{
    app.MapControllers();
}

app.Run();