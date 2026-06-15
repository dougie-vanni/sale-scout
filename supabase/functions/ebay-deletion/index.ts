/**
 * eBay Marketplace Account Deletion notification endpoint.
 *
 * Required for eBay Production API compliance. Handles:
 *   GET  ?challenge_code=xxx  — ownership verification (returns SHA-256 hash)
 *   POST <deletion payload>   — account deletion notice (acknowledged, ignored;
 *                               this app stores no eBay user account data)
 *
 * VERIFICATION_TOKEN must match the value entered in the eBay developer portal
 * (Application Keys → Alerts & Notifications → Verification token).
 */

const VERIFICATION_TOKEN = "salescout-ebay-b7ef0f3e";

async function sha256hex(input: string): Promise<string> {
  const data = new TextEncoder().encode(input);
  const buf  = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(buf))
    .map(b => b.toString(16).padStart(2, "0"))
    .join("");
}

Deno.serve(async (req: Request) => {
  const url         = new URL(req.url);
  const endpointUrl = `${url.origin}${url.pathname}`;

  // eBay ownership challenge
  if (req.method === "GET") {
    const challengeCode = url.searchParams.get("challenge_code");
    if (!challengeCode) {
      return new Response("Missing challenge_code", { status: 400 });
    }
    const hash = await sha256hex(challengeCode + VERIFICATION_TOKEN + endpointUrl);
    return new Response(JSON.stringify({ challengeResponse: hash }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Account deletion notification — acknowledge only
  if (req.method === "POST") {
    return new Response(null, { status: 200 });
  }

  return new Response("Method not allowed", { status: 405 });
});
