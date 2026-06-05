import { T } from "../tokens";

export default function Footer() {

  const productLinks = [
    "ATS Analyser",
    "Gap Analyser",
    "AI Rewrites",
    "Recruiter Simulation",
    "AI Career Coach",
  ];

  const companyLinks = ["About", "Blog", "Careers", "Press"];

  const legalLinks = [
    "Privacy Policy",
    "Terms of Service",
    "Cookie Policy",
    "Refund Policy",
  ];

  const socialIcons = [
    { name: "LinkedIn", icon: "in" },
    { name: "Twitter", icon: "𝕏" },
    { name: "GitHub", icon: "gh" },
  ];

  return (
    <footer style={{ background: "#0d0d1a", padding: "60px 40px 40px" }}>
      <div
        style={{
          maxWidth: 1200,
          margin: "0 auto",
          display: "grid",
          gridTemplateColumns: "2fr 1fr 1fr 1fr",
          gap: 48,
          marginBottom: 48,
        }}
      >
        {/* Brand Column */}
        <div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              marginBottom: 10,
            }}
          >
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                background: T.gradientBrand,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#ffffff",
                fontSize: 16,
                fontWeight: 700,
              }}
            >
              ✦
            </div>
            <div
              style={{
                fontSize: 14,
                fontWeight: 700,
                color: "#f0f0ff",
              }}
            >
              AI Career Intelligence
            </div>
          </div>

          <div
            style={{
              fontSize: 13,
              color: "#52526a",
              lineHeight: 1.6,
              maxWidth: 260,
              marginBottom: 20,
            }}
          >
            AI-powered resume analysis for the modern job seeker. Built for Indian professionals, trusted by 12,400+ people across Bangalore, Hyderabad, Mumbai, and Delhi.
          </div>

          <div style={{ display: "flex", gap: 12 }}>
            {socialIcons.map((social) => (
              <a
                key={social.name}
                href="#"
                title={social.name}
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: T.radiusXs,
                  background: "#1a1a2e",
                  color: "#52526a",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 14,
                  fontWeight: 700,
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                  textDecoration: "none",
                }}
                onMouseEnter={(e) => {
                  const el = e.currentTarget as HTMLAnchorElement;
                  el.style.background = "#252545";
                  el.style.color = "#a1a1c0";
                }}
                onMouseLeave={(e) => {
                  const el = e.currentTarget as HTMLAnchorElement;
                  el.style.background = "#1a1a2e";
                  el.style.color = "#52526a";
                }}
              >
                {social.icon}
              </a>
            ))}
          </div>
        </div>

        {/* Product Column */}
        <div>
          <div
            style={{
              fontSize: 12,
              fontWeight: 700,
              color: "#f0f0ff",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginBottom: 14,
            }}
          >
            Product
          </div>
          {productLinks.map((link) => (
            <a
              key={link}
              href="#"
              style={{
                display: "block",
                fontSize: 13,
                color: "#52526a",
                marginBottom: 8,
                cursor: "pointer",
                textDecoration: "none",
                transition: "color 0.2s ease",
              }}
              onMouseEnter={(e) => {
                const el = e.currentTarget as HTMLAnchorElement;
                el.style.color = "#a1a1c0";
              }}
              onMouseLeave={(e) => {
                const el = e.currentTarget as HTMLAnchorElement;
                el.style.color = "#52526a";
              }}
            >
              {link}
            </a>
          ))}
        </div>

        {/* Company Column */}
        <div>
          <div
            style={{
              fontSize: 12,
              fontWeight: 700,
              color: "#f0f0ff",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginBottom: 14,
            }}
          >
            Company
          </div>
          {companyLinks.map((link) => (
            <a
              key={link}
              href="#"
              style={{
                display: "block",
                fontSize: 13,
                color: "#52526a",
                marginBottom: 8,
                cursor: "pointer",
                textDecoration: "none",
                transition: "color 0.2s ease",
              }}
              onMouseEnter={(e) => {
                const el = e.currentTarget as HTMLAnchorElement;
                el.style.color = "#a1a1c0";
              }}
              onMouseLeave={(e) => {
                const el = e.currentTarget as HTMLAnchorElement;
                el.style.color = "#52526a";
              }}
            >
              {link}
            </a>
          ))}
        </div>

        {/* Legal Column */}
        <div>
          <div
            style={{
              fontSize: 12,
              fontWeight: 700,
              color: "#f0f0ff",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginBottom: 14,
            }}
          >
            Legal
          </div>
          {legalLinks.map((link) => (
            <a
              key={link}
              href="#"
              style={{
                display: "block",
                fontSize: 13,
                color: "#52526a",
                marginBottom: 8,
                cursor: "pointer",
                textDecoration: "none",
                transition: "color 0.2s ease",
              }}
              onMouseEnter={(e) => {
                const el = e.currentTarget as HTMLAnchorElement;
                el.style.color = "#a1a1c0";
              }}
              onMouseLeave={(e) => {
                const el = e.currentTarget as HTMLAnchorElement;
                el.style.color = "#52526a";
              }}
            >
              {link}
            </a>
          ))}
        </div>
      </div>

      {/* Bottom Bar */}
      <div
        style={{
          borderTop: "1px solid #1e1e3a",
          paddingTop: 24,
          fontSize: 12,
          color: "#333358",
          textAlign: "center",
        }}
      >
        © 2026 Resume Intelligence Platform. All rights reserved. Built with ❤ in India.
      </div>
    </footer>
  );
}
