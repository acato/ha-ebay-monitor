import crypto from "crypto";

const TOKEN = process.env.EBAY_VERIFICATION_TOKEN;
const ENDPOINT = process.env.EBAY_ENDPOINT_URL;

export default function handler(req, res) {
  res.setHeader("Content-Type", "application/json");

  if (!TOKEN || !ENDPOINT) {
    return res.status(500).json({ error: "Missing env vars" });
  }

  // GET — eBay challenge verification
  if (req.method === "GET") {
    const code = req.query.challenge_code;
    if (!code) {
      return res.status(400).json({ error: "Missing challenge_code" });
    }
    const hash = crypto
      .createHash("sha256")
      .update(code + TOKEN + ENDPOINT)
      .digest("hex");
    return res.status(200).json({ challengeResponse: hash });
  }

  // POST — account deletion notification (just acknowledge)
  if (req.method === "POST") {
    return res.status(200).json({ status: "received" });
  }

  return res.status(405).json({ error: "Method not allowed" });
}
