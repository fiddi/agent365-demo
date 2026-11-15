using System.Net.Http;

namespace DemoAgent.Diagnostics;

/// <summary>
/// Diagnostic handler for the MSAL HTTP client: when a token request fails, logs the requested
/// grant_type and scope (never secrets, assertions or tokens). Enabled only when
/// Diagnostics:LogTokenScopes = true.
/// </summary>
public sealed class TokenScopeLoggingHandler(ILogger<TokenScopeLoggingHandler> logger) : DelegatingHandler
{
    protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        string? grantType = null, scope = null;
        if (request.Content is not null && request.RequestUri?.AbsolutePath.EndsWith("/token", StringComparison.OrdinalIgnoreCase) == true)
        {
            var body = await request.Content.ReadAsStringAsync(cancellationToken);
            foreach (var pair in body.Split('&'))
            {
                var kv = pair.Split('=', 2);
                if (kv.Length != 2) continue;
                if (kv[0] == "grant_type") grantType = Uri.UnescapeDataString(kv[1]);
                if (kv[0] == "scope") scope = Uri.UnescapeDataString(kv[1].Replace('+', ' '));
            }
        }

        var response = await base.SendAsync(request, cancellationToken);
        if (!response.IsSuccessStatusCode && (grantType is not null || scope is not null))
        {
            logger.LogWarning("Token request failed ({Status}): grant_type={GrantType} scope={Scope}",
                (int)response.StatusCode, grantType, scope);
        }
        return response;
    }
}
