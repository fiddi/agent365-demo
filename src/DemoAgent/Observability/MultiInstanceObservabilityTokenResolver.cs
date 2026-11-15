using System;
using System.Collections.Concurrent;
using System.Threading.Tasks;
using Microsoft.Extensions.Configuration;

namespace Agent365.Samples.Observability;

/// <summary>
/// Resolves Agent 365 observability tokens for every agent instance created from the blueprint
/// (e.g. "Ava" and "Peter Helfer"). Keeps one <see cref="ObservabilityAppTokenProvider"/> per agent
/// identity; each provider gets an app-only token for exactly that identity via the shared blueprint
/// credential. Exports for other tenants are rejected.
/// </summary>
internal sealed class MultiInstanceObservabilityTokenResolver : IDisposable
{
    private readonly IConfiguration _configuration;
    private readonly string _tenantId;
    private readonly ConcurrentDictionary<string, Lazy<ObservabilityAppTokenProvider>> _providers = new(StringComparer.OrdinalIgnoreCase);

    private MultiInstanceObservabilityTokenResolver(IConfiguration configuration, string tenantId)
    {
        _configuration = configuration;
        _tenantId = tenantId;
    }

    public static MultiInstanceObservabilityTokenResolver? CreateIfEnabled(IConfiguration configuration)
    {
        if (!ObservabilityAppTokenFactory.IsAgent365ExporterEnabled(configuration)) return null;
        // Validates the configuration once (blueprint, tenant, default agent id, credential).
        using var probe = ObservabilityAppTokenFactory.Create(configuration);
        return new MultiInstanceObservabilityTokenResolver(configuration, configuration["Agent365Observability:TenantId"]!);
    }

    public Task<string?> ResolveAsync(string agentId, string tenantId)
    {
        if (!Guid.TryParse(agentId, out _) || !string.Equals(tenantId, _tenantId, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException("Observability export tenant/agent does not match the configured blueprint tenant.");
        }
        var provider = _providers.GetOrAdd(agentId,
            id => new Lazy<ObservabilityAppTokenProvider>(() => ObservabilityAppTokenFactory.Create(_configuration, id))).Value;
        return provider.ResolveAsync(agentId, tenantId);
    }

    public void Dispose()
    {
        foreach (var p in _providers.Values)
        {
            if (p.IsValueCreated) p.Value.Dispose();
        }
    }
}
