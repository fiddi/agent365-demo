using Microsoft.Extensions.AI;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace DemoAgent.Tools;

/// <summary>
/// Code-level guardrail for outbound email: wraps every MCP tool that can send mail and rejects
/// the call if any recipient is outside the allowed domains. The system prompt says the same,
/// but this check also holds when the model is tricked (e.g. by prompt injection in an email).
/// </summary>
public static partial class RecipientGuard
{
    // Tool names from mcp_MailTools that send mail somewhere (send, reply, forward, drafts that may be sent).
    private static readonly string[] SendingVerbs = ["send", "reply", "forward"];

    [GeneratedRegex(@"[A-Za-z0-9._%+\-']+@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})")]
    private static partial Regex EmailRegex();

    public static IList<AITool> Wrap(IEnumerable<AITool> tools, IReadOnlyCollection<string> allowedDomains, ILogger? logger)
    {
        return tools.Select(t =>
            t is AIFunction f && SendingVerbs.Any(v => f.Name.Contains(v, StringComparison.OrdinalIgnoreCase))
                ? new GuardedFunction(f, allowedDomains, logger)
                : t).ToList();
    }

    /// <summary>Returns the email addresses in the arguments whose domain is not allowed.</summary>
    public static IReadOnlyList<string> FindExternalRecipients(AIFunctionArguments arguments, IReadOnlyCollection<string> allowedDomains)
    {
        var json = JsonSerializer.Serialize(arguments.ToDictionary(kv => kv.Key, kv => kv.Value));
        return EmailRegex().Matches(json)
            .Select(m => m.Value)
            .Where(addr =>
            {
                var domain = addr[(addr.LastIndexOf('@') + 1)..];
                return !allowedDomains.Any(d =>
                    domain.Equals(d, StringComparison.OrdinalIgnoreCase) ||
                    domain.EndsWith("." + d, StringComparison.OrdinalIgnoreCase));
            })
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    private sealed class GuardedFunction(AIFunction inner, IReadOnlyCollection<string> allowedDomains, ILogger? logger)
        : DelegatingAIFunction(inner)
    {
        protected override ValueTask<object?> InvokeCoreAsync(AIFunctionArguments arguments, CancellationToken cancellationToken)
        {
            var external = FindExternalRecipients(arguments, allowedDomains);
            if (external.Count > 0)
            {
                logger?.LogWarning("Blocked tool {Tool}: external recipient(s) {Count}", Name, external.Count);
                return ValueTask.FromResult<object?>(
                    $"BLOCKED by policy: email can only be sent to {string.Join(", ", allowedDomains)} addresses. " +
                    $"Not allowed: {string.Join(", ", external)}. Tell the user that you cannot send to external recipients.");
            }
            return base.InvokeCoreAsync(arguments, cancellationToken);
        }
    }
}
