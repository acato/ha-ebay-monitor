export default function handler(req, res) {
  res.status(200).json({
    status: "ok",
    service: "ebay-marketplace-deletion",
    token_configured: !!process.env.EBAY_VERIFICATION_TOKEN,
    endpoint_configured: !!process.env.EBAY_ENDPOINT_URL,
  });
}
