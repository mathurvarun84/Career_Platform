import React from "react";
import { useAuthStore } from "../store/authStore";
import { supabase } from "../lib/supabase";
import { useWindowSize } from "../hooks/useWindowSize";
import { T } from "../tokens";

function useCountUp(target: number, duration = 1400): number {
  const [count, setCount] = React.useState(0);
  React.useEffect(() => {
    if (!target) return;
    let start = 0;
    const step = 16;
    const increment = target / (duration / step);
    const timer = setInterval(() => {
      start += increment;
      if (start >= target) { setCount(target); clearInterval(timer); }
      else { setCount(Math.floor(start)); }
    }, step);
    return () => clearInterval(timer);
  }, [target, duration]);
  return count;
}

interface LandingPageProps {
  onNavigateToUpload: () => void;
  onOpenAuthModal?: () => void;
}

export default function LandingPage({ onNavigateToUpload, onOpenAuthModal }: LandingPageProps) {
  const user = useAuthStore((state) => state.user);

  const handleStartAnalysis = () => {
    // User is authenticated → go to upload
    if (user) {
      onNavigateToUpload();
    } else {
      // User not authenticated → show auth modal
      // After they sign in, the RequireAuth wrapper will handle showing the upload page
      onOpenAuthModal?.();
      // Also navigate away from landing so upload page shows
      onNavigateToUpload();
    }
  };
  return (
    <div style={{ background: T.bgPage, minHeight: "100vh" }}>
      {/* Section 1: Nav Bar */}
      <NavBar onOpenAuthModal={onOpenAuthModal} />

      {/* Section 2: Hero Section */}
      <HeroSection onStartAnalysis={handleStartAnalysis} />

      {/* Section 3: Hero Product Card */}
      <HeroProductCard />

      {/* Section 4: Metrics Strip */}
      <MetricsStrip />

      {/* Section 5: Company Logos */}
      <CompanyLogos />

      {/* Section 6: Success Stories */}
      <SuccessStories />

      {/* Section 7: Features */}
      <Features />

      {/* Section 8: How It Works */}
      <HowItWorks />

      {/* Section 9: Comparison Table */}
      <ComparisonSection />

      {/* Section 10: Screenshots Gallery */}
      <ScreenshotsGallery />

      {/* Section 11: Testimonials */}
      <TestimonialsSection />

      {/* Section 12: Final CTA */}
      <FinalCTA onStartAnalysis={handleStartAnalysis} />
    </div>
  );
}

// ============================================================================
// Section 1: Nav Bar
// ============================================================================

const NavBar = ({
  onOpenAuthModal,
}: {
  onOpenAuthModal?: () => void;
}) => {
  const user = useAuthStore((state) => state.user);
  const { isMobile } = useWindowSize();
  const [hoveredLink, setHoveredLink] = React.useState<string | null>(null);

  const navLinks = [
    "Features",
    "How It Works",
    "Success Stories",
  ];

  return (
    <nav
      style={{
        position: "sticky",
        top: 0,
        zIndex: 50,
        background: "rgba(255,255,255,0.96)",
        backdropFilter: "blur(20px) saturate(180%)",
        borderBottom: `1px solid ${T.border}`,
        boxShadow: T.shadowTopBar,
      }}
    >
      <div
        style={{
          maxWidth: T.maxWidth,
          margin: "0 auto",
          padding: isMobile ? "0 20px" : "0 40px",
          height: T.topBarHeight,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 10,
              background: T.gradientBrand,
              boxShadow: `0 3px 8px ${T.primaryLight.replace(
                "#",
                "rgba(91,95,199,"
              )}0.35)`,
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
          <div>
            <div
              style={{
                fontSize: 14,
                fontWeight: 700,
                color: T.textPrimary,
                letterSpacing: "-0.02em",
              }}
            >
              {isMobile ? "AI Career" : "AI Career Intelligence"}
            </div>
            {!isMobile && (
              <div
                style={{
                  fontSize: 10,
                  fontWeight: 400,
                  color: T.textMuted,
                }}
              >
                Powered by Advanced AI
              </div>
            )}
          </div>
        </div>

        {/* Center Nav Links — hidden on mobile */}
        <div style={{ display: isMobile ? "none" : "flex", gap: 28 }}>
          {navLinks.map((link) => (
            <button
              key={link}
              onMouseEnter={() => setHoveredLink(link)}
              onMouseLeave={() => setHoveredLink(null)}
              style={{
                fontSize: 13,
                fontWeight: 500,
                color: hoveredLink === link ? T.primary : T.textSecondary,
                background: "transparent",
                border: "none",
                cursor: "pointer",
                textDecoration: hoveredLink === link ? "underline" : "none",
                textDecorationColor: hoveredLink === link ? T.primary : undefined,
                transition: "color 0.2s ease",
              }}
              aria-label={`Navigate to ${link}`}
            >
              {link}
            </button>
          ))}
        </div>

        {/* Right Button — Sign In / Sign Out */}
        {user ? (
          <button
            onClick={() => { void supabase.auth.signOut(); }}
            style={{
              padding: "9px 20px",
              borderRadius: T.radiusXs,
              fontSize: 13,
              fontWeight: 600,
              background: "transparent",
              color: T.textSecondary,
              border: `1.5px solid ${T.border}`,
              cursor: "pointer",
              transition: "all 0.2s ease",
            }}
            onMouseEnter={(e) => {
              const el = e.currentTarget as HTMLButtonElement;
              el.style.borderColor = T.borderStrong;
              el.style.color = T.textPrimary;
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget as HTMLButtonElement;
              el.style.borderColor = T.border;
              el.style.color = T.textSecondary;
            }}
          >
            Sign Out
          </button>
        ) : (
          <button
            onClick={onOpenAuthModal}
            style={{
              padding: "9px 20px",
              borderRadius: T.radiusXs,
              fontSize: 13,
              fontWeight: 700,
              background: T.primary,
              color: "#ffffff",
              border: "none",
              boxShadow: T.shadowPrimarySm,
              cursor: "pointer",
              transition: "transform 0.1s, box-shadow 0.1s",
            }}
            onMouseEnter={(e) => {
              const el = e.currentTarget as HTMLButtonElement;
              el.style.background = T.primaryDark;
              el.style.transform = "translateY(-2px)";
              el.style.boxShadow = `0 6px 0 #3a3d9a, 0 12px 28px rgba(91,95,199,0.32)`;
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget as HTMLButtonElement;
              el.style.background = T.primary;
              el.style.transform = "";
              el.style.boxShadow = T.shadowPrimarySm;
            }}
            onMouseDown={(e) => {
              const el = e.currentTarget as HTMLButtonElement;
              el.style.transform = "translateY(3px)";
              el.style.boxShadow = "0 1px 0 #3a3d9a";
            }}
            onMouseUp={(e) => {
              const el = e.currentTarget as HTMLButtonElement;
              el.style.transform = "translateY(-2px)";
              el.style.boxShadow = `0 6px 0 #3a3d9a, 0 12px 28px rgba(91,95,199,0.32)`;
            }}
          >
            Sign In
          </button>
        )}
      </div>
    </nav>
  );
};

// ============================================================================
// Section 2: Hero Section
// ============================================================================

const HeroSection = ({ onStartAnalysis }: { onStartAnalysis: () => void }) => {
  const { isMobile, isTablet } = useWindowSize();
  return (
    <section
      style={{
        background: T.gradientHeroPage,
        padding: isMobile ? "48px 20px 40px" : isTablet ? "64px 40px 56px" : "80px 40px 60px",
        position: "relative",
        overflow: "hidden",
        textAlign: "center",
      }}
    >
      {/* Radial Glow Decorations */}
      <div
        style={{
          position: "absolute",
          top: -100,
          right: -100,
          width: 600,
          height: 600,
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(91,95,199,0.08) 0%, transparent 70%)",
          pointerEvents: "none",
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: -80,
          left: -80,
          width: 400,
          height: 400,
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(124,58,237,0.06) 0%, transparent 70%)",
          pointerEvents: "none",
        }}
      />

      <div style={{ position: "relative", zIndex: 1 }}>
        {/* Section Badge */}
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "5px 14px",
            borderRadius: T.radiusPill,
            background: "#ffffff",
            border: `1.5px solid ${T.primaryMid}`,
            fontSize: 12,
            fontWeight: 700,
            color: T.primary,
            boxShadow: T.shadowSm,
            marginBottom: 20,
          }}
        >
          ✦ AI-Powered Resume Analysis
        </div>

        {/* Hero Headline */}
        <div
          style={{
            fontFamily: "'DM Serif Display', serif",
            fontSize: isMobile ? 36 : isTablet ? 44 : 58,
            lineHeight: 1.07,
            letterSpacing: "-0.025em",
            color: T.textPrimary,
            marginBottom: 20,
          }}
        >
          The AI platform that helps you get hired{" "}
          <em
            style={{
              fontStyle: "italic",
              color: T.primary,
            }}
          >
            faster.
          </em>
        </div>

        {/* Sub-headline */}
        <div
          style={{
            fontSize: 18,
            color: T.textSecondary,
            maxWidth: 540,
            margin: "0 auto 32px",
            lineHeight: 1.65,
          }}
        >
          Resume scoring, gap analysis, AI rewrites, mock interviews — all grounded in your actual resume and the job you want.
        </div>

        {/* CTA Row */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 12,
            marginBottom: 16,
            flexWrap: "wrap",
          }}
        >
          <button
            onClick={onStartAnalysis}
            style={{
              padding: "14px 32px",
              borderRadius: T.radiusLg,
              fontSize: 15,
              fontWeight: 700,
              background: T.primary,
              color: "#ffffff",
              border: "none",
              boxShadow: T.shadowPrimary,
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              cursor: "pointer",
              transition: "all 0.2s ease",
            }}
            onMouseEnter={(e) => {
              const el = e.currentTarget as HTMLButtonElement;
              el.style.transform = "translateY(-2px)";
              el.style.boxShadow = "0 6px 0 #3a3d9a, 0 12px 32px rgba(91,95,199,0.35)";
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget as HTMLButtonElement;
              el.style.transform = "translateY(0)";
              el.style.boxShadow = T.shadowPrimary;
            }}
            onMouseDown={(e) => {
              const el = e.currentTarget as HTMLButtonElement;
              el.style.transform = "translateY(3px)";
              el.style.boxShadow = "0 1px 0 #3a3d9a";
            }}
            onMouseUp={(e) => {
              const el = e.currentTarget as HTMLButtonElement;
              el.style.transform = "translateY(-2px)";
              el.style.boxShadow = T.shadowPrimary;
            }}
          >
            Start Free Analysis →
          </button>

          <button
            style={{
              padding: "14px 28px",
              borderRadius: T.radiusLg,
              fontSize: 15,
              fontWeight: 600,
              color: T.textSecondary,
              background: "#ffffff",
              border: `1.5px solid ${T.border}`,
              boxShadow: T.shadowSm,
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              cursor: "pointer",
              transition: "all 0.2s ease",
            }}
            onMouseEnter={(e) => {
              const el = e.currentTarget as HTMLButtonElement;
              el.style.borderColor = T.primary;
              el.style.color = T.primary;
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget as HTMLButtonElement;
              el.style.borderColor = T.border;
              el.style.color = T.textSecondary;
            }}
            aria-label="Watch 90 second demo"
          >
            ▶ Watch 90s demo
          </button>
        </div>

        {/* Trust Line */}
        <div
          style={{
            fontSize: 13,
            color: T.textMuted,
          }}
        >
          Free to try · No credit card · Results in 60 seconds
        </div>
      </div>
    </section>
  );
};

// ============================================================================
// Section 3: Hero Product Card
// ============================================================================

const HeroProductCard = () => {
  const [isHovered, setIsHovered] = React.useState(false);
  const { isMobile } = useWindowSize();
  const heroScore = useCountUp(91, 1400);

  const keywords = [
    { label: "React", found: true },
    { label: "TypeScript", found: true },
    { label: "Node.js", found: true },
    { label: "AWS", found: false },
    { label: "CI/CD", found: true },
    { label: "Docker", found: false },
    { label: "GraphQL", found: true },
  ];

  if (isMobile) return null;

  return (
    <div
      style={{
        maxWidth: 860,
        margin: "48px auto 0",
        background: T.bgCard,
        border: `1.5px solid ${T.border}`,
        borderRadius: T.radiusXl,
        padding: 32,
        boxShadow: T.shadowXl,
        transition: "transform 0.3s ease, box-shadow 0.3s ease",
        transform: isHovered ? "scale(1.015)" : "scale(1)",
        cursor: "default",
        willChange: "transform",
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Score Row */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 20,
        }}
      >
        <div>
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: T.textMuted,
              textTransform: "uppercase",
              letterSpacing: "0.07em",
              marginBottom: 6,
            }}
          >
            ATS SCORE
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 72,
                fontWeight: 600,
                color: T.textPrimary,
                lineHeight: 1,
                letterSpacing: "-0.03em",
              }}
            >
              {heroScore}
            </span>
            <span
              style={{
                fontSize: 22,
                color: T.textMuted,
                fontWeight: 400,
              }}
            >
              /100
            </span>
          </div>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              padding: "4px 12px",
              borderRadius: T.radiusPill,
              background: T.emeraldLight,
              border: `1px solid ${T.emeraldBorder}`,
              fontSize: 12,
              fontWeight: 700,
              color: T.emerald,
              marginTop: 8,
            }}
          >
            ✓ Excellent match
          </div>
        </div>

        {/* Score Ring SVG */}
        <svg width="120" height="120" viewBox="0 0 120 120" style={{ flexShrink: 0 }}>
          <defs>
            <linearGradient
              id="scoreGradient"
              x1="0%"
              y1="0%"
              x2="100%"
              y2="0%"
            >
              <stop offset="0%" stopColor={T.primary} />
              <stop offset="100%" stopColor={T.violet} />
            </linearGradient>
          </defs>
          {/* Background circle */}
          <circle
            cx="60"
            cy="60"
            r="50"
            fill="none"
            stroke={T.border}
            strokeWidth="9"
          />
          {/* Progress arc — 91% = 286 314 circumference */}
          <circle
            cx="60"
            cy="60"
            r="50"
            fill="none"
            stroke="url(#scoreGradient)"
            strokeWidth="9"
            strokeLinecap="round"
            strokeDasharray="286 314"
            strokeDashoffset="78"
            transform="rotate(-90 60 60)"
          />
        </svg>
      </div>

      {/* Keyword Chips Row */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 8,
          marginBottom: 20,
        }}
      >
        {keywords.map((kw, i) => (
          <KeywordChip
            key={kw.label}
            label={kw.label}
            found={kw.found}
            index={i}
          />
        ))}
      </div>

      {/* Before/After Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 16,
          borderTop: `1px solid ${T.border}`,
          paddingTop: 20,
          marginTop: 4,
        }}
      >
        <div
          style={{
            background: "#fff5f5",
            borderLeft: "3px solid #fca5a5",
            borderRadius: "0 8px 8px 0",
            padding: "12px 14px",
          }}
        >
          <div
            style={{
              fontSize: 9,
              fontWeight: 800,
              color: T.rose,
              textTransform: "uppercase",
              letterSpacing: "0.07em",
              marginBottom: 6,
            }}
          >
            BEFORE
          </div>
          <div
            style={{
              fontSize: 12,
              color: T.textMuted,
              lineHeight: 1.6,
            }}
          >
            Responsible for writing code and working on various projects across teams.
          </div>
        </div>

        <div
          style={{
            background: "#f0fdf4",
            borderLeft: "3px solid #6ee7b7",
            borderRadius: "0 8px 8px 0",
            padding: "12px 14px",
          }}
        >
          <div
            style={{
              fontSize: 9,
              fontWeight: 800,
              color: T.emerald,
              textTransform: "uppercase",
              letterSpacing: "0.07em",
              marginBottom: 6,
            }}
          >
            AFTER
          </div>
          <div
            style={{
              fontSize: 12,
              color: T.textPrimary,
              fontWeight: 500,
              lineHeight: 1.6,
            }}
          >
            Engineered 3 cross-functional React/Node.js features adopted by 40K+ users, reducing page load time 34% via code-splitting and lazy loading.
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// Section 4: Metrics Strip
// ============================================================================

const MetricsStrip = () => {
  const { isTablet } = useWindowSize();
  const metrics = [
    { value: "12", label: "Resume scoring dimensions" },
    { value: "3", label: "AI rewrite styles per bullet" },
    { value: "60s", label: "Full analysis time" },
    { value: "4", label: "Recruiter persona types" },
  ];

  return (
    <section
      style={{
        background: T.bgCard,
        borderTop: `1px solid ${T.border}`,
        borderBottom: `1px solid ${T.border}`,
        padding: "32px 40px",
      }}
    >
      <div
        style={{
          maxWidth: T.maxWidth,
          margin: "0 auto",
          display: "grid",
          gridTemplateColumns: isTablet ? "repeat(2, 1fr)" : "repeat(4, 1fr)",
          gap: isTablet ? "16px 0" : 0,
        }}
      >
        {metrics.map((metric, i) => (
          <MetricCard
            key={i}
            value={metric.value}
            label={metric.label}
            isFirst={i === 0}
          />
        ))}
      </div>
    </section>
  );
};

// ============================================================================
// Section 5: Company Logos
// ============================================================================

const CompanyLogos = () => {
  const companies = [
    "Google",
    "McKinsey",
    "Stripe",
    "Amazon",
    "Sequoia",
    "Notion",
    "Meta",
  ];

  return (
    <section
      style={{
        padding: "48px 40px",
        textAlign: "center",
      }}
    >
      <div
        style={{
          fontSize: 11,
          fontWeight: 700,
          color: T.textMuted,
          textTransform: "uppercase",
          letterSpacing: "0.07em",
          marginBottom: 20,
        }}
      >
        Professionals from these companies have improved their resumes
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 40,
          flexWrap: "wrap",
        }}
      >
        {companies.map((company) => (
          <CompanyLogo key={company} name={company} />
        ))}
      </div>
    </section>
  );
};

// ============================================================================
// Section 6: Success Stories
// ============================================================================

const SuccessStories = () => {
  const { isMobile, isTablet } = useWindowSize();
  return (
    <section style={{ padding: isMobile ? "40px 20px" : "60px 40px" }}>
      {/* Section Header */}
      <div style={{ textAlign: "center", marginBottom: 48 }}>
        <div
          style={{
            fontSize: 12,
            fontWeight: 700,
            color: T.primary,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            marginBottom: 10,
          }}
        >
          SOCIAL PROOF
        </div>
        <div
          style={{
            fontSize: 36,
            fontWeight: 700,
            color: T.textPrimary,
            letterSpacing: "-0.025em",
            marginBottom: 12,
          }}
        >
          Real results from real professionals
        </div>
        <div
          style={{
            fontSize: 17,
            color: T.textSecondary,
            lineHeight: 1.65,
          }}
        >
          See how others transformed their job search
        </div>
      </div>

      {/* Two-Column Grid */}
      <div
        style={{
          maxWidth: T.maxWidth,
          margin: "0 auto",
          display: "grid",
          gridTemplateColumns: isTablet ? "1fr" : "1fr 1fr",
          gap: 24,
        }}
      >
        <SuccessCard
          person="Sarah M."
          title="Senior Product Designer"
          company="Google"
          avatarUrl="https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=200&h=200&fit=crop&crop=face"
          avatarFallback="SM"
          avatarGradient={`linear-gradient(135deg, ${T.primary}, ${T.violet})`}
          beforeScore={42}
          afterScore={91}
          cardGradient={`linear-gradient(135deg, ${T.emeraldLight}, #d1fae5)`}
          cardBorder={T.emeraldBorder}
          scoreLabelColor={T.emerald}
          completionBg={T.emerald}
          outcomeColor={T.emerald}
          quote="Went from 42 to 91 ATS score in 10 minutes. The AI rewrites turned my generic bullet points into specific, metrics-driven achievements."
          outcome="Landed Google PM interview within 2 weeks"
        />

        <SuccessCard
          person="James C."
          title="Backend Engineer"
          company="Stripe"
          avatarUrl="https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=200&h=200&fit=crop&crop=face"
          avatarFallback="JC"
          avatarGradient={`linear-gradient(135deg, ${T.violet}, ${T.primary})`}
          beforeScore={58}
          afterScore={94}
          cardGradient={`linear-gradient(135deg, ${T.primaryLight}, #ede9fe)`}
          cardBorder={T.primaryMid}
          scoreLabelColor={T.primary}
          completionBg={T.primary}
          outcomeColor={T.primary}
          quote="The gap analysis showed exactly which keywords I was missing for Stripe's infrastructure roles. Fixed them, re-ran the analysis — score jumped 36 points."
          outcome="3 Stripe-level offers in 3 weeks"
        />
      </div>
    </section>
  );
};

// ============================================================================
// Sub-components
// ============================================================================

const KeywordChip = ({ label, found, index = 0 }: { label: string; found: boolean; index?: number }) => (
  <span
    style={{
      padding: "5px 12px",
      borderRadius: T.radiusPill,
      fontSize: 12,
      fontWeight: 600,
      background: found ? T.emeraldLight : T.roseLight,
      color: found ? T.emerald : T.rose,
      border: `1px solid ${found ? T.emeraldBorder : T.roseBorder}`,
      animation: "chipReveal 0.4s ease-out both",
      animationDelay: `${index * 60}ms`,
    }}
  >
    {found ? "✓ " : "✗ "}
    {label}
  </span>
);

const MetricCard = ({
  value,
  label,
  isFirst,
}: {
  value: string;
  label: string;
  isFirst?: boolean;
}) => (
  <div
    style={{
      padding: "0 32px",
      textAlign: "center",
      borderLeft: isFirst ? "none" : `1px solid ${T.border}`,
    }}
  >
    <div
      style={{
        fontSize: 32,
        fontWeight: 800,
        color: T.textPrimary,
        letterSpacing: "-0.03em",
        fontVariantNumeric: "tabular-nums",
      }}
    >
      {value}
    </div>
    <div
      style={{
        fontSize: 12,
        color: T.textMuted,
        marginTop: 3,
        fontWeight: 500,
      }}
    >
      {label}
    </div>
  </div>
);

const CompanyLogo = ({ name }: { name: string }) => (
  <span
    style={{
      fontSize: 18,
      fontWeight: 800,
      color: T.textDisabled,
      opacity: 0.4,
      filter: "grayscale(1)",
    }}
  >
    {name}
  </span>
);

// ============================================================================
// Section 7: Features
// ============================================================================

const Features = () => {
  const { isMobile, isTablet } = useWindowSize();
  return (
    <section style={{ padding: isMobile ? "48px 20px" : "80px 40px", maxWidth: "1200px", margin: "0 auto" }}>
      {/* Section Header */}
      <div style={{ textAlign: "center", marginBottom: 64 }}>
        <div
          style={{
            fontSize: 12,
            fontWeight: 700,
            color: T.primary,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            marginBottom: 10,
          }}
        >
          FEATURES
        </div>
        <div
          style={{
            fontSize: 36,
            fontWeight: 700,
            color: T.textPrimary,
            letterSpacing: "-0.025em",
            lineHeight: 1.2,
            marginBottom: 14,
          }}
        >
          Everything you need to get hired
        </div>
        <div
          style={{
            fontSize: 17,
            color: T.textSecondary,
            lineHeight: 1.65,
            maxWidth: 580,
            margin: "0 auto",
          }}
        >
          A complete AI-powered toolkit that covers every stage of the resume optimisation process.
        </div>
      </div>

      {/* Feature 1: ATS Intelligence */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: isTablet ? "1fr" : "1fr 1fr",
          gap: isTablet ? "32px" : "64px",
          alignItems: "center",
          marginBottom: "80px",
        }}
      >
        {/* Visual - Left */}
        <div
          style={{
            background: T.bgCard,
            border: `1.5px solid ${T.border}`,
            borderRadius: T.radiusXl,
            padding: 32,
            boxShadow: T.shadowMd,
            transition: "box-shadow 0.2s ease",
            cursor: "default",
          }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.boxShadow = T.shadowLg; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.boxShadow = T.shadowMd; }}
        >
          {/* Score Row */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 24,
            }}
          >
            <div>
              <div
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 56,
                  fontWeight: 600,
                  color: T.primary,
                  lineHeight: 1,
                }}
              >
                91
              </div>
            </div>
            <svg width="80" height="80" viewBox="0 0 80 80">
              <defs>
                <linearGradient
                  id="featureGradient1"
                  x1="0%"
                  y1="0%"
                  x2="100%"
                  y2="0%"
                >
                  <stop offset="0%" stopColor={T.primary} />
                  <stop offset="100%" stopColor={T.violet} />
                </linearGradient>
              </defs>
              <circle cx="40" cy="40" r="32" fill="none" stroke={T.border} strokeWidth="7" />
              <circle
                cx="40"
                cy="40"
                r="32"
                fill="none"
                stroke="url(#featureGradient1)"
                strokeWidth="7"
                strokeLinecap="round"
                strokeDasharray="191 201"
                transform="rotate(-90 40 40)"
              />
            </svg>
          </div>

          {/* Progress Bars */}
          <ProgressBar label="ATS Compatibility" value={91} gradient="linear-gradient(90deg, #5b5fc7, #818cf8)" />
          <ProgressBar label="Keyword Match" value={87} gradient="linear-gradient(90deg, #7c3aed, #a78bfa)" />
          <ProgressBar label="Format Score" value={94} gradient="linear-gradient(90deg, #059669, #34d399)" />
          <ProgressBar label="Impact Score" value={82} gradient="linear-gradient(90deg, #d97706, #fbbf24)" />
        </div>

        {/* Text - Right */}
        <div>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "5px 14px",
              borderRadius: 20,
              background: "#eef0ff",
              color: T.primary,
              fontSize: 12,
              fontWeight: 700,
              marginBottom: 16,
            }}
          >
            📊 ATS Intelligence
          </div>
          <div
            style={{
              fontSize: 30,
              fontWeight: 700,
              letterSpacing: "-0.025em",
              color: T.textPrimary,
              marginBottom: 14,
              lineHeight: 1.25,
            }}
          >
            Beat every ATS filter — guaranteed
          </div>
          <div
            style={{
              fontSize: 16,
              color: T.textSecondary,
              lineHeight: 1.7,
              marginBottom: 20,
            }}
          >
            Our multi-layer ATS analysis scores your resume across 12 dimensions, identifies every keyword gap, and tells you exactly what to fix — in plain English.
          </div>
          <FeatureListItem text="Real-time keyword matching against the exact job description" />
          <FeatureListItem text="Format and structure scoring across 50+ ATS systems" />
          <FeatureListItem text="Instant fix suggestions ranked by impact on your score" />
        </div>
      </div>

      {/* Feature 2: Gap Analysis */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: isTablet ? "1fr" : "1fr 1fr",
          gap: isTablet ? "32px" : "64px",
          alignItems: "center",
          marginBottom: "80px",
        }}
      >
        {/* Text - Left */}
        <div>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "5px 14px",
              borderRadius: 20,
              background: "#f5f3ff",
              color: T.violet,
              fontSize: 12,
              fontWeight: 700,
              marginBottom: 16,
            }}
          >
            🎯 Gap Analysis
          </div>
          <div
            style={{
              fontSize: 30,
              fontWeight: 700,
              letterSpacing: "-0.025em",
              color: T.textPrimary,
              marginBottom: 14,
              lineHeight: 1.25,
            }}
          >
            Know exactly what's missing — and why it matters
          </div>
          <div
            style={{
              fontSize: 16,
              color: T.textSecondary,
              lineHeight: 1.7,
              marginBottom: 20,
            }}
          >
            We cross-reference your resume against 200+ signals from the job description, identify missing skills, under-evidenced claims, and structural weaknesses your human reviewer would miss.
          </div>
          <FeatureListItem text="Skill gap heatmap — see which gaps cost you the most" />
          <FeatureListItem text="Evidence gap detection — find bullets with no proof of impact" />
          <FeatureListItem text="Structural analysis — section ordering, length, and density" />
        </div>

        {/* Visual - Right */}
        <div
          style={{
            background: T.bgCard,
            border: `1.5px solid ${T.border}`,
            borderRadius: T.radiusXl,
            padding: 32,
            boxShadow: T.shadowMd,
            transition: "box-shadow 0.2s ease",
            cursor: "default",
          }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.boxShadow = T.shadowLg; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.boxShadow = T.shadowMd; }}
        >
          <div
            style={{
              fontSize: 14,
              fontWeight: 700,
              color: T.textPrimary,
              marginBottom: 16,
            }}
          >
            Skill Gap Analysis
          </div>
          <SkillRow skill="React / Next.js" found={true} />
          <SkillRow skill="System Design" found={true} />
          <SkillRow skill="AWS / Cloud" found={false} />
          <SkillRow skill="TypeScript" found={true} />
          <SkillRow skill="Kubernetes" found={false} />
        </div>
      </div>

      {/* Feature 3: AI Rewrites */}
      <div
        style={{
          background: "linear-gradient(135deg, #eef0ff, #f5f3ff)",
          borderRadius: T.radiusXl,
          padding: 52,
          border: `1.5px solid #dde0ff`,
        }}
      >
        {/* Header Row */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            marginBottom: 32,
            gap: 40,
          }}
        >
          <div>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "5px 14px",
                borderRadius: 20,
                background: T.bgCard,
                color: T.primary,
                fontSize: 12,
                fontWeight: 700,
                border: `1.5px solid #dde0ff`,
                boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
                marginBottom: 10,
              }}
            >
              ✦ AI Rewrites
            </div>
            <div
              style={{
                fontSize: 30,
                fontWeight: 700,
                color: T.textPrimary,
                letterSpacing: "-0.025em",
                lineHeight: 1.25,
              }}
            >
              From generic to remarkable — instantly
            </div>
          </div>
          <div
            style={{
              fontSize: 15,
              color: T.textSecondary,
              lineHeight: 1.7,
              maxWidth: 380,
            }}
          >
            Three rewrite styles — balanced, aggressive, and top-1% — each grounded in your actual experience. No hallucinations. No generic advice.
          </div>
        </div>

        {/* Before/After Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 20,
            maxWidth: 800,
            margin: "0 auto",
          }}
        >
          {/* Before */}
          <div
            style={{
              background: T.bgCard,
              borderRadius: T.radiusMd,
              padding: 24,
              border: `1.5px solid ${T.roseBorder}`,
              boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
            }}
          >
            <div
              style={{
                fontSize: 9,
                fontWeight: 800,
                textTransform: "uppercase",
                letterSpacing: "0.07em",
                color: T.rose,
                marginBottom: 12,
                display: "flex",
                alignItems: "center",
                gap: 5,
              }}
            >
              ✗ BEFORE
            </div>
            <div
              style={{
                background: T.roseLight,
                borderRadius: T.radiusXs,
                padding: "8px 12px",
                marginBottom: 8,
                fontSize: 13,
                color: T.textMuted,
                lineHeight: 1.6,
              }}
            >
              • Responsible for managing team projects and ensuring delivery.
            </div>
            <div
              style={{
                background: T.roseLight,
                borderRadius: T.radiusXs,
                padding: "8px 12px",
                fontSize: 13,
                color: T.textMuted,
                lineHeight: 1.6,
              }}
            >
              • Worked on improving system performance and fixing bugs.
            </div>
          </div>

          {/* After */}
          <div
            style={{
              background: T.bgCard,
              borderRadius: T.radiusMd,
              padding: 24,
              border: `1.5px solid ${T.emeraldBorder}`,
              boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
            }}
          >
            <div
              style={{
                fontSize: 9,
                fontWeight: 800,
                textTransform: "uppercase",
                letterSpacing: "0.07em",
                color: T.emerald,
                marginBottom: 12,
              }}
            >
              ✓ AFTER — Top 1% Rewrite
            </div>
            <div
              style={{
                background: T.emeraldLight,
                borderRadius: T.radiusXs,
                padding: "8px 12px",
                marginBottom: 8,
                fontSize: 13,
                color: T.textPrimary,
                fontWeight: 500,
                lineHeight: 1.6,
              }}
            >
              • Led cross-functional delivery of 4 product launches, reducing average sprint cycle by 22% across a 9-person engineering team.
            </div>
            <div
              style={{
                background: T.emeraldLight,
                borderRadius: T.radiusXs,
                padding: "8px 12px",
                fontSize: 13,
                color: T.textPrimary,
                fontWeight: 500,
                lineHeight: 1.6,
              }}
            >
              • Diagnosed and resolved P0 memory leak in production API, cutting p99 latency from 2.1s → 340ms for 80K daily active users.
            </div>
          </div>
        </div>

        {/* Feature 4: AI Mock Interview */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: isTablet ? "1fr" : "1fr 1fr",
            gap: isTablet ? "32px" : "64px",
            alignItems: "center",
            marginTop: "80px",
          }}
        >
          {/* Text — Left */}
          <div>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "5px 14px",
                borderRadius: 20,
                background: T.amberLight,
                color: T.amber,
                fontSize: 12,
                fontWeight: 700,
                marginBottom: 16,
              }}
            >
              🎯 AI Mock Interview
            </div>
            <div
              style={{
                fontSize: 30,
                fontWeight: 700,
                letterSpacing: "-0.025em",
                color: T.textPrimary,
                marginBottom: 14,
                lineHeight: 1.25,
              }}
            >
              Practice the interview before it's real
            </div>
            <div
              style={{
                fontSize: 16,
                color: T.textSecondary,
                lineHeight: 1.7,
                marginBottom: 20,
              }}
            >
              3 behavioral questions generated from your actual resume and the target job. Real-time feedback on ownership, impact, and communication — calibrated to the company's known hiring bar.
            </div>
            <FeatureListItem text="Questions grounded in your resume — no generic prompts" />
            <FeatureListItem text="Company-specific scoring: Amazon LPs, Google Googleyness, and more" />
            <FeatureListItem text="Anti-pattern detection — catch 'we did...' vagueness before the real interview" />
          </div>

          {/* Visual — Right */}
          <div
            style={{
              background: T.bgCard,
              border: `1.5px solid ${T.border}`,
              borderRadius: T.radiusXl,
              padding: 28,
              boxShadow: T.shadowMd,
            }}
          >
            {/* Session header */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 20,
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 700, color: T.textPrimary }}>
                Mock Interview · Amazon · Senior SDE
              </div>
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 5,
                  padding: "3px 10px",
                  borderRadius: 20,
                  background: T.emeraldLight,
                  border: `1px solid ${T.emeraldBorder}`,
                  fontSize: 11,
                  fontWeight: 700,
                  color: T.emerald,
                }}
              >
                Q 2 / 3
              </div>
            </div>

            {/* Question card */}
            <div
              style={{
                background: T.bgSubtle,
                borderRadius: T.radiusMd,
                padding: "14px 16px",
                marginBottom: 16,
                border: `1px solid ${T.border}`,
              }}
            >
              <div
                style={{
                  fontSize: 10,
                  fontWeight: 800,
                  color: T.textMuted,
                  textTransform: "uppercase",
                  letterSpacing: "0.07em",
                  marginBottom: 6,
                }}
              >
                OWNERSHIP · LP: Deliver Results
              </div>
              <div style={{ fontSize: 13, color: T.textPrimary, lineHeight: 1.6 }}>
                Tell me about a time you drove a project to completion despite significant blockers. What was your personal role in unblocking it?
              </div>
            </div>

            {/* Feedback card */}
            <div
              style={{
                background: T.bgCard,
                border: `1.5px solid ${T.primaryMid}`,
                borderRadius: T.radiusMd,
                padding: "14px 16px",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: 10,
                }}
              >
                <div style={{ fontSize: 12, fontWeight: 700, color: T.textPrimary }}>
                  Signal Strength
                </div>
                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    padding: "2px 10px",
                    borderRadius: 20,
                    background: T.primaryLight,
                    color: T.primary,
                    fontSize: 11,
                    fontWeight: 700,
                  }}
                >
                  Developing
                </div>
              </div>
              <div
                style={{
                  fontSize: 12,
                  color: T.textSecondary,
                  lineHeight: 1.6,
                  marginBottom: 8,
                }}
              >
                Good story structure. Tip: your result appeared in the last sentence — lead with the impact to make it land harder.
              </div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "6px 10px",
                  borderRadius: T.radiusXs,
                  background: T.amberLight,
                  border: `1px solid #fde68a`,
                }}
              >
                <span style={{ fontSize: 11, fontWeight: 800, color: T.amber }}>⚠</span>
                <span style={{ fontSize: 11, color: T.amber, fontWeight: 600 }}>
                  Pattern: Impact Buried — move outcome to the top
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

// ============================================================================
// Section 8: How It Works
// ============================================================================

const HowItWorks = () => {
  const { isMobile, isTablet } = useWindowSize();
  return (
    <section style={{ background: T.bgCard, padding: isMobile ? "48px 20px" : "80px 40px" }}>
      <div style={{ maxWidth: T.maxWidth, margin: "0 auto" }}>
        {/* Section Header */}
        <div style={{ textAlign: "center", marginBottom: 56 }}>
          <div
            style={{
              fontSize: 12,
              fontWeight: 700,
              color: T.primary,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginBottom: 10,
            }}
          >
            HOW IT WORKS
          </div>
          <div
            style={{
              fontSize: 36,
              fontWeight: 700,
              color: T.textPrimary,
              letterSpacing: "-0.025em",
              marginBottom: 14,
            }}
          >
            From upload to insights in 60 seconds
          </div>
          <div
            style={{
              fontSize: 17,
              color: T.textSecondary,
              lineHeight: 1.65,
            }}
          >
            No setup, no integrations. Paste your resume, add the job description, and get a full analysis.
          </div>
        </div>

        {/* 3-Column Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: isTablet ? "1fr" : "repeat(3, 1fr)",
            gap: isTablet ? "32px" : "40px",
          }}
        >
          <Step
            number="1"
            icon="📄"
            title="Upload Your Resume"
            body="Paste or upload your resume in any format. We'll parse it instantly and identify all key sections."
          />
          <Step
            number="2"
            icon="🎯"
            title="Add the Job Description"
            body="Paste the job posting URL or full text. Our AI extracts every requirement, keyword, and signal that matters."
          />
          <Step
            number="3"
            icon="📈"
            title="Get Your Full Analysis"
            body="In under 60 seconds, receive your ATS score, gap analysis, AI rewrites, and a recruiter simulation — all grounded in your specific resume and role."
          />
        </div>
      </div>
    </section>
  );
};

// ============================================================================
// Section 9: Comparison Table
// ============================================================================

const ComparisonSection = () => {
  const rows = [
    {
      feature: "ATS Score Analysis",
      traditional: { type: "negative", label: "No" },
      free: { type: "neutral", label: "Basic only" },
      rip: { type: "positive", label: "12-dimension" },
    },
    {
      feature: "Keyword Gap Detection",
      traditional: { type: "negative", label: "No" },
      free: { type: "neutral", label: "Partial" },
      rip: { type: "positive", label: "Full JD match" },
    },
    {
      feature: "AI Bullet Rewrites",
      traditional: { type: "negative", label: "No" },
      free: { type: "negative", label: "No" },
      rip: { type: "positive", label: "3 rewrite styles" },
    },
    {
      feature: "Recruiter Simulation",
      traditional: { type: "negative", label: "No" },
      free: { type: "negative", label: "No" },
      rip: { type: "positive", label: "4 persona types" },
    },
    {
      feature: "AI Mock Interview",
      traditional: { type: "negative", label: "No" },
      free: { type: "negative", label: "No" },
      rip: { type: "positive", label: "JD-grounded, 3 questions" },
    },
    {
      feature: "Grounded in your resume",
      traditional: { type: "neutral", label: "Sometimes" },
      free: { type: "negative", label: "Generic" },
      rip: { type: "positive", label: "Always specific" },
    },
    {
      feature: "Results time",
      traditional: { type: "neutral", label: "Days" },
      free: { type: "positive", label: "Instant" },
      rip: { type: "positive", label: "60 seconds" },
    },
    {
      feature: "Cost",
      traditional: { type: "negative", label: "₹2,000–5,000" },
      free: { type: "positive", label: "Free" },
      rip: { type: "positive", label: "Free to try" },
    },
  ];

  return (
    <section style={{ background: T.bgSubtle, padding: "80px 40px" }}>
      <div style={{ maxWidth: T.maxWidth, margin: "0 auto" }}>
        {/* Section Header */}
        <div style={{ textAlign: "center", marginBottom: 48 }}>
          <div
            style={{
              fontSize: 12,
              fontWeight: 700,
              color: T.primary,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginBottom: 10,
            }}
          >
            WHY US
          </div>
          <div
            style={{
              fontSize: 36,
              fontWeight: 700,
              color: T.textPrimary,
              letterSpacing: "-0.025em",
              marginBottom: 12,
            }}
          >
            Not all resume tools are equal
          </div>
          <div
            style={{
              fontSize: 17,
              color: T.textSecondary,
              lineHeight: 1.65,
            }}
          >
            See how Resume Intelligence compares to traditional review and free alternatives.
          </div>
        </div>

        {/* Table Container */}
        <div
          style={{
            maxWidth: 896,
            margin: "0 auto",
            borderRadius: T.radiusXl,
            border: `1.5px solid ${T.border}`,
            overflow: "hidden",
            boxShadow: T.shadowMd,
          }}
        >
          {/* Header Row */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              borderBottom: `1px solid ${T.border}`,
            }}
          >
            <div
              style={{
                background: T.bgCard,
                padding: "20px 28px",
                borderRight: `1px solid ${T.border}`,
              }}
            >
              <div style={{ fontSize: 14, fontWeight: 700, color: T.textPrimary, marginBottom: 4 }}>
                Traditional Review
              </div>
              <div style={{ fontSize: 12, color: T.textMuted }}>Expert feedback</div>
            </div>
            <div
              style={{
                background: T.bgCard,
                padding: "20px 28px",
                borderRight: `1px solid ${T.border}`,
              }}
            >
              <div style={{ fontSize: 14, fontWeight: 700, color: T.textPrimary, marginBottom: 4 }}>
                Free Tools
              </div>
              <div style={{ fontSize: 12, color: T.textMuted }}>Limited scope</div>
            </div>
            <div
              style={{
                background: "linear-gradient(160deg, #eef0ff, #f5f3ff)",
                padding: "20px 28px",
                position: "relative",
              }}
            >
              <div style={{ fontSize: 14, fontWeight: 700, color: T.textPrimary, marginBottom: 4 }}>
                Resume Intelligence ✨
              </div>
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  padding: "2px 8px",
                  borderRadius: 999,
                  background: T.primary,
                  color: "#fff",
                  fontSize: 10,
                  fontWeight: 700,
                  marginTop: 4,
                }}
              >
                RECOMMENDED
              </div>
            </div>
          </div>

          {/* Data Rows */}
          {rows.map((row, idx) => (
            <div
              key={idx}
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                borderTop: idx === 0 ? "none" : `1px solid ${T.border}`,
              }}
            >
              <div
                style={{
                  background: T.bgCard,
                  padding: "14px 28px",
                  borderRight: `1px solid ${T.border}`,
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <ComparisonItem type={row.traditional.type as any} label={row.traditional.label} />
              </div>
              <div
                style={{
                  background: T.bgCard,
                  padding: "14px 28px",
                  borderRight: `1px solid ${T.border}`,
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <ComparisonItem type={row.free.type as any} label={row.free.label} />
              </div>
              <div
                style={{
                  background: "linear-gradient(160deg, #eef0ff, #f5f3ff)",
                  padding: "14px 28px",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <ComparisonItem type={row.rip.type as any} label={row.rip.label} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

// ============================================================================
// Section 10: Screenshots Gallery
// ============================================================================

const ScreenshotsGallery = () => {
  const { isMobile, isTablet } = useWindowSize();
  return (
    <section style={{ padding: isMobile ? "48px 20px" : "80px 40px" }}>
      <div style={{ maxWidth: T.maxWidth, margin: "0 auto" }}>
        {/* Section Header */}
        <div style={{ textAlign: "center", marginBottom: 48 }}>
          <div
            style={{
              fontSize: 36,
              fontWeight: 700,
              color: T.textPrimary,
              letterSpacing: "-0.025em",
              marginBottom: 12,
            }}
          >
            Every insight you need, beautifully designed
          </div>
          <div
            style={{
              fontSize: 17,
              color: T.textSecondary,
              lineHeight: 1.65,
            }}
          >
            A complete dashboard built for serious professionals
          </div>
        </div>

        {/* 2-Column Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: isTablet ? "1fr" : "1fr 1fr",
            gap: 24,
          }}
        >
          {/* Card 1 - Overview Dashboard */}
          <div
            style={{
              background: T.bgCard,
              border: `1.5px solid ${T.border}`,
              borderRadius: T.radiusXl,
              overflow: "hidden",
              boxShadow: T.shadowXl,
              transition: "box-shadow 0.2s ease",
              cursor: "default",
            }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.boxShadow = "0 24px 64px rgba(0,0,0,0.15)"; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.boxShadow = T.shadowXl; }}
          >
            {/* Icon Header */}
            <div
              style={{
                padding: "16px 20px",
                display: "flex",
                alignItems: "center",
                gap: 10,
                borderBottom: `1px solid ${T.border}`,
              }}
            >
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: T.radiusXs,
                  background: T.primaryLight,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: T.primary,
                  fontSize: 18,
                  flexShrink: 0,
                }}
              >
                📊
              </div>
              <div style={{ fontSize: 14, fontWeight: 700, color: T.textPrimary }}>
                Complete Overview Dashboard
              </div>
            </div>

            {/* Preview Area */}
            <div
              style={{
                padding: 24,
                background: "linear-gradient(135deg, #f8f8fc, #eef0ff)",
                minHeight: 200,
              }}
            >
              {/* Mini Metric Cards */}
              <div
                style={{
                  display: "flex",
                  gap: 10,
                  marginBottom: 16,
                }}
              >
                <div
                  style={{
                    background: T.bgCard,
                    borderRadius: T.radiusXs,
                    padding: "12px 14px",
                    border: `1px solid ${T.border}`,
                    flex: 1,
                  }}
                >
                  <div style={{ fontSize: 10, fontWeight: 700, color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 2 }}>
                    ATS SCORE
                  </div>
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 24, fontWeight: 700, color: T.primary }}>
                    91
                  </div>
                </div>
                <div
                  style={{
                    background: T.bgCard,
                    borderRadius: T.radiusXs,
                    padding: "12px 14px",
                    border: `1px solid ${T.border}`,
                    flex: 1,
                  }}
                >
                  <div style={{ fontSize: 10, fontWeight: 700, color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 2 }}>
                    JD MATCH
                  </div>
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 24, fontWeight: 700, color: T.violet }}>
                    89%
                  </div>
                </div>
                <div
                  style={{
                    background: T.bgCard,
                    borderRadius: T.radiusXs,
                    padding: "12px 14px",
                    border: `1px solid ${T.border}`,
                    flex: 1,
                  }}
                >
                  <div style={{ fontSize: 10, fontWeight: 700, color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 2 }}>
                    MARKET RANK
                  </div>
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 24, fontWeight: 700, color: T.emerald }}>
                    Top 8%
                  </div>
                </div>
              </div>

              {/* Priority Actions */}
              <div>
                <ActionItem dot={T.rose} text="Add measurable impact metrics to 3 bullets" />
                <ActionItem dot={T.amber} text='Include missing keyword: "system design"' />
                <ActionItem dot={T.emerald} text="Resume length optimised ✓" />
              </div>
            </div>
          </div>

          {/* Card 2 - Recruiter Simulation */}
          <div
            style={{
              background: T.bgCard,
              border: `1.5px solid ${T.border}`,
              borderRadius: T.radiusXl,
              overflow: "hidden",
              boxShadow: T.shadowXl,
              transition: "box-shadow 0.2s ease",
              cursor: "default",
            }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.boxShadow = "0 24px 64px rgba(0,0,0,0.15)"; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.boxShadow = T.shadowXl; }}
          >
            {/* Icon Header */}
            <div
              style={{
                padding: "16px 20px",
                display: "flex",
                alignItems: "center",
                gap: 10,
                borderBottom: `1px solid ${T.border}`,
              }}
            >
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: T.radiusXs,
                  background: "#f5f0ff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: T.violet,
                  fontSize: 18,
                  flexShrink: 0,
                }}
              >
                👥
              </div>
              <div style={{ fontSize: 14, fontWeight: 700, color: T.textPrimary }}>
                Recruiter 6-Second Scan Simulation
              </div>
            </div>

            {/* Preview Area */}
            <div style={{ padding: 16 }}>
              {/* Decision Badge */}
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "6px 14px",
                  borderRadius: 20,
                  background: T.roseLight,
                  border: `1.5px solid ${T.roseBorder}`,
                  fontSize: 13,
                  fontWeight: 700,
                  color: "#991b1b",
                  marginBottom: 12,
                }}
              >
                ✗ Not Shortlisted
              </div>

              {/* Persona Card */}
              <div
                style={{
                  background: "linear-gradient(135deg, #fff1f0, #fff7f0)",
                  border: `1.5px solid ${T.roseBorder}`,
                  borderRadius: T.radiusMd,
                  padding: 20,
                  marginBottom: 12,
                }}
              >
                <div style={{ fontSize: 12, fontWeight: 600, color: T.textMuted, marginBottom: 8 }}>
                  Senior Engineering Manager at FAANG
                </div>

                {/* Concerns */}
                <ConcernItem text="No evidence of scale — missing user/revenue numbers" />
                <ConcernItem text='Keyword gap: "distributed systems" not mentioned' />
                <ConcernItem text="Senior role requires 3 more years of experience" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

// ============================================================================
// Section 11: Testimonials
// ============================================================================

const TestimonialsSection = () => {
  const { isMobile, isTablet } = useWindowSize();
  return (
    <section style={{ background: T.bgSubtle, padding: isMobile ? "48px 20px" : "80px 40px" }}>
      <div style={{ maxWidth: T.maxWidth, margin: "0 auto" }}>
        {/* Section Header */}
        <div style={{ textAlign: "center", marginBottom: 48 }}>
          <div
            style={{
              fontSize: 12,
              fontWeight: 700,
              color: T.primary,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginBottom: 10,
            }}
          >
            TESTIMONIALS
          </div>
          <div
            style={{
              fontSize: 36,
              fontWeight: 700,
              color: T.textPrimary,
              letterSpacing: "-0.025em",
              marginBottom: 12,
            }}
          >
            Loved by professionals across India
          </div>
          <div
            style={{
              fontSize: 17,
              color: T.textSecondary,
              lineHeight: 1.65,
            }}
          >
            Real results from real people — not curated outliers.
          </div>
        </div>

        {/* 3-Column Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: isTablet ? "1fr" : "repeat(3, 1fr)",
            gap: 20,
          }}
        >
          <TestimonialCard
            quote="Went from 42 to 91 ATS score in 10 minutes. The gap analysis told me exactly which keywords were killing my applications. Three interviews in the first week."
            name="Priya M."
            role="Product Manager, Bangalore"
            outcome="→ Hired at Flipkart within 3 weeks"
            initials="PM"
            avatarGradient={`linear-gradient(135deg, ${T.primary}, ${T.violet})`}
          />

          <TestimonialCard
            quote="The AI rewrites are incredible. It took my generic 'responsible for...' bullets and turned them into specific, metrics-driven achievements. I felt like I had a senior career coach reviewing every line."
            name="James K."
            role="Senior Software Engineer, Hyderabad"
            outcome="→ 40% salary increase at new role"
            initials="JK"
            avatarGradient={`linear-gradient(135deg, ${T.violet}, ${T.primary})`}
            featured={true}
          />

          <TestimonialCard
            quote="Finally understand why my resume wasn't getting responses. The recruiter simulation showed me exactly how a FAANG hiring manager reads it — and it was eye-opening. Fixed the issues, got 4 callbacks in a week."
            name="Sarah L."
            role="Data Scientist, Pune"
            outcome="→ Offer from Google DeepMind team"
            initials="SL"
            avatarGradient={`linear-gradient(135deg, ${T.emerald}, ${T.primary})`}
          />
        </div>
      </div>
    </section>
  );
};

// ============================================================================
// Section 12: Final CTA
// ============================================================================

const FinalCTA = ({ onStartAnalysis }: { onStartAnalysis: () => void }) => {
  const { isMobile } = useWindowSize();
  return (
    <section
      style={{
        background: T.gradientBrand,
        padding: isMobile ? "48px 20px" : "80px 40px",
        textAlign: "center",
      }}
    >
      <div style={{ maxWidth: 600, margin: "0 auto" }}>
        <div
          style={{
            fontFamily: "'DM Serif Display', serif",
            fontSize: 44,
            color: "#ffffff",
            letterSpacing: "-0.02em",
            marginBottom: 16,
            lineHeight: 1.1,
          }}
        >
          Ready to land your next role?
        </div>

        <div
          style={{
            fontSize: 17,
            color: "rgba(255,255,255,0.75)",
            lineHeight: 1.65,
            maxWidth: 520,
            margin: "0 auto 32px",
          }}
        >
          Join 1,000+ professionals who've already improved their resume scores — and landed more interviews.
        </div>

        <button
          onClick={onStartAnalysis}
          style={{
            padding: "14px 32px",
            borderRadius: T.radiusMd,
            background: "#ffffff",
            color: T.primary,
            fontSize: 15,
            fontWeight: 700,
            border: "none",
            cursor: "pointer",
            fontFamily: "inherit",
            boxShadow: "0 4px 0 rgba(0,0,0,0.15), 0 8px 24px rgba(0,0,0,0.2)",
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            transition: "transform 0.1s, box-shadow 0.1s",
            marginBottom: 16,
          }}
          onMouseEnter={(e) => {
            const el = e.currentTarget as HTMLButtonElement;
            el.style.background = "#eef0ff";
            el.style.transform = "translateY(-2px)";
            el.style.boxShadow = "0 6px 0 rgba(0,0,0,0.15), 0 14px 32px rgba(0,0,0,0.22)";
          }}
          onMouseLeave={(e) => {
            const el = e.currentTarget as HTMLButtonElement;
            el.style.background = "#ffffff";
            el.style.transform = "";
            el.style.boxShadow = "0 4px 0 rgba(0,0,0,0.15), 0 8px 24px rgba(0,0,0,0.2)";
          }}
          onMouseDown={(e) => {
            const el = e.currentTarget as HTMLButtonElement;
            el.style.transform = "translateY(3px)";
            el.style.boxShadow = "0 1px 0 rgba(0,0,0,0.15)";
          }}
          onMouseUp={(e) => {
            const el = e.currentTarget as HTMLButtonElement;
            el.style.transform = "translateY(-2px)";
            el.style.boxShadow = "0 6px 0 rgba(0,0,0,0.15), 0 14px 32px rgba(0,0,0,0.22)";
          }}
        >
          Start Free Analysis →
        </button>

        <div
          style={{
            fontSize: 13,
            color: "rgba(255,255,255,0.5)",
          }}
        >
          Free to try · No credit card · Results in 60 seconds
        </div>
      </div>
    </section>
  );
};

interface SuccessCardProps {
  person: string;
  title: string;
  company: string;
  avatarUrl: string;
  avatarFallback: string;
  avatarGradient: string;
  beforeScore: number;
  afterScore: number;
  cardGradient: string;
  cardBorder: string;
  scoreLabelColor: string;
  completionBg: string;
  outcomeColor: string;
  quote: string;
  outcome: string;
}

// ============================================================================
// Sub-components (Day 3)
// ============================================================================

const FeatureListItem = ({ text }: { text: string }) => (
  <div
    style={{
      display: "flex",
      alignItems: "flex-start",
      gap: 10,
      fontSize: 14,
      color: T.textSecondary,
      marginBottom: 10,
    }}
  >
    <div
      style={{
        width: 18,
        height: 18,
        borderRadius: "50%",
        background: T.primaryLight,
        color: T.primary,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: 10,
        fontWeight: 800,
        flexShrink: 0,
        marginTop: 1,
      }}
    >
      ✓
    </div>
    <span style={{ lineHeight: 1.6 }}>{text}</span>
  </div>
);

const ProgressBar = ({
  label,
  value,
  gradient,
}: {
  label: string;
  value: number;
  gradient: string;
}) => (
  <div style={{ marginBottom: 12 }}>
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        marginBottom: 4,
      }}
    >
      <span style={{ fontSize: 12, fontWeight: 600, color: T.textSecondary }}>
        {label}
      </span>
      <span style={{ fontSize: 12, fontWeight: 700, color: T.textPrimary }}>
        {value}%
      </span>
    </div>
    <div
      style={{
        height: 5,
        background: T.bgSubtle,
        borderRadius: T.radiusXs,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          height: "100%",
          borderRadius: T.radiusXs,
          background: gradient,
          width: `${value}%`,
          transition: "width 0.6s ease",
        }}
      />
    </div>
  </div>
);

const SkillRow = ({ skill, found }: { skill: string; found: boolean }) => (
  <div
    style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "10px 14px",
      borderRadius: T.radiusXs,
      marginBottom: 8,
      background: found ? T.emeraldLight : T.roseLight,
      border: `1px solid ${found ? T.emeraldBorder : T.roseBorder}`,
    }}
  >
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div
        style={{
          width: 18,
          height: 18,
          borderRadius: "50%",
          background: found ? T.emeraldLight : T.roseLight,
          border: `1px solid ${found ? T.emeraldBorder : T.roseBorder}`,
          color: found ? T.emerald : T.rose,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 10,
          fontWeight: 800,
        }}
      >
        {found ? "✓" : "✗"}
      </div>
      <span style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary }}>
        {skill}
      </span>
    </div>
    <span
      style={{
        background: found ? T.emeraldLight : T.roseLight,
        color: found ? T.emerald : T.rose,
        border: `1px solid ${found ? T.emeraldBorder : T.roseBorder}`,
        padding: "2px 8px",
        borderRadius: T.radiusPill,
        fontSize: 11,
        fontWeight: 700,
      }}
    >
      {found ? "Found" : "Missing"}
    </span>
  </div>
);

const ComparisonItem = ({
  type,
  label,
}: {
  type: "positive" | "negative" | "neutral";
  label: string;
}) => {
  const icon = type === "positive" ? "✓" : type === "negative" ? "✗" : "~";
  const color =
    type === "positive" ? T.emerald : type === "negative" ? T.rose : T.amber;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        fontSize: 13,
        color: T.textSecondary,
      }}
    >
      <span
        style={{
          color,
          fontSize: 14,
          fontWeight: 800,
          flexShrink: 0,
        }}
      >
        {icon}
      </span>
      <span>{label}</span>
    </div>
  );
};

const Step = ({
  number,
  icon,
  title,
  body,
}: {
  number: string;
  icon: string;
  title: string;
  body: string;
}) => (
  <div style={{ textAlign: "center" }}>
    <div
      style={{
        fontFamily: "'DM Serif Display', serif",
        fontSize: 56,
        background: T.gradientBrand,
        WebkitBackgroundClip: "text",
        WebkitTextFillColor: "transparent",
        marginBottom: 4,
        lineHeight: 1,
      }}
    >
      {number}
    </div>
    <div
      style={{
        width: 64,
        height: 64,
        borderRadius: T.radiusLg,
        background: T.gradientBrand,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        margin: "0 auto 16px",
        fontSize: 26,
        color: "#fff",
        boxShadow: "0 6px 20px rgba(91,95,199,0.3)",
      }}
    >
      {icon}
    </div>
    <div style={{ fontSize: 18, fontWeight: 700, color: T.textPrimary, marginBottom: 8 }}>
      {title}
    </div>
    <div style={{ fontSize: 14, color: T.textSecondary, lineHeight: 1.65 }}>
      {body}
    </div>
  </div>
);

const TestimonialCard = ({
  quote,
  name,
  role,
  outcome,
  initials,
  avatarGradient,
  featured,
}: {
  quote: string;
  name: string;
  role: string;
  outcome: string;
  initials: string;
  avatarGradient: string;
  featured?: boolean;
}) => {
  const defaultShadow = featured
    ? "0 0 0 3px rgba(91,95,199,0.10), 0 4px 12px rgba(0,0,0,0.07)"
    : "0 2px 6px rgba(0,0,0,0.04)";
  return (
  <div
    style={{
      background: T.bgCard,
      border: featured ? `1.5px solid ${T.primary}` : `1.5px solid ${T.border}`,
      borderRadius: T.radiusLg,
      padding: 28,
      boxShadow: defaultShadow,
      display: "flex",
      flexDirection: "column",
      gap: 16,
      transition: "box-shadow 0.2s ease, transform 0.2s ease",
      cursor: "default",
    }}
    onMouseEnter={(e) => {
      (e.currentTarget as HTMLDivElement).style.boxShadow = T.shadowLg;
      (e.currentTarget as HTMLDivElement).style.transform = "translateY(-2px)";
    }}
    onMouseLeave={(e) => {
      (e.currentTarget as HTMLDivElement).style.boxShadow = defaultShadow;
      (e.currentTarget as HTMLDivElement).style.transform = "translateY(0)";
    }}
  >
    {featured && (
      <div
        style={{
          display: "inline-flex",
          padding: "3px 10px",
          borderRadius: 20,
          background: T.primaryLight,
          color: T.primary,
          fontSize: 11,
          fontWeight: 700,
          alignSelf: "flex-start",
        }}
      >
        ✦ Featured
      </div>
    )}
    <div style={{ color: "#f59e0b", fontSize: 14, letterSpacing: 2 }}>
      ★★★★★
    </div>
    <div
      style={{
        fontSize: 14,
        color: T.textPrimary,
        lineHeight: 1.65,
        fontStyle: "italic",
        flexGrow: 1,
      }}
    >
      "{quote}"
    </div>
    <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: "auto" }}>
      <div
        style={{
          width: 40,
          height: 40,
          borderRadius: "50%",
          background: avatarGradient,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 14,
          fontWeight: 700,
          color: "#ffffff",
          border: "2px solid #fff",
          boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
          flexShrink: 0,
        }}
      >
        {initials}
      </div>
      <div>
        <div style={{ fontSize: 13, fontWeight: 700, color: T.textPrimary }}>
          {name}
        </div>
        <div style={{ fontSize: 12, color: T.textMuted }}>{role}</div>
        <div style={{ fontSize: 11, fontWeight: 700, color: T.emerald, marginTop: 2 }}>
          {outcome}
        </div>
      </div>
    </div>
  </div>
  );
};

const ActionItem = ({ dot, text }: { dot: string; text: string }) => (
  <div
    style={{
      display: "flex",
      alignItems: "center",
      gap: 8,
      padding: "8px 10px",
      borderRadius: T.radiusXs,
      marginBottom: 6,
      background: T.bgSubtle,
      border: `1px solid ${T.border}`,
      fontSize: 12,
      color: T.textSecondary,
    }}
  >
    <div
      style={{
        width: 6,
        height: 6,
        borderRadius: "50%",
        background: dot,
        flexShrink: 0,
      }}
    />
    <span>{text}</span>
  </div>
);

const ConcernItem = ({ text }: { text: string }) => (
  <div
    style={{
      display: "flex",
      alignItems: "flex-start",
      gap: 6,
      marginBottom: 6,
    }}
  >
    <div
      style={{
        width: 4,
        height: 4,
        borderRadius: "50%",
        background: T.rose,
        marginTop: 6,
        flexShrink: 0,
      }}
    />
    <span style={{ fontSize: 12, color: T.textSecondary, lineHeight: 1.5 }}>
      {text}
    </span>
  </div>
);

// ============================================================================

const SuccessCard = ({
  person,
  title,
  company,
  avatarUrl,
  avatarFallback,
  avatarGradient,
  beforeScore,
  afterScore,
  cardGradient,
  cardBorder,
  scoreLabelColor,
  completionBg,
  outcomeColor,
  quote,
  outcome,
}: SuccessCardProps) => {
  const [imgError, setImgError] = React.useState(false);

  return (
    <div
      style={{
        borderRadius: T.radiusXl,
        padding: 36,
        background: cardGradient,
        border: `1.5px solid ${cardBorder}`,
        position: "relative",
        overflow: "hidden",
        transition: "box-shadow 0.2s ease, transform 0.2s ease",
        cursor: "default",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.boxShadow = T.shadowLg;
        (e.currentTarget as HTMLDivElement).style.transform = "translateY(-2px)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.boxShadow = "none";
        (e.currentTarget as HTMLDivElement).style.transform = "translateY(0)";
      }}
    >
      {/* Person Info */}
      <div style={{ display: "flex", gap: 16, marginBottom: 20 }}>
        {imgError ? (
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: "50%",
              background: avatarGradient,
              border: "2px solid #fff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 18,
              fontWeight: 700,
              color: "#ffffff",
              flexShrink: 0,
            }}
          >
            {avatarFallback}
          </div>
        ) : (
          <img
            src={avatarUrl}
            alt={person}
            onError={() => setImgError(true)}
            style={{
              width: 48,
              height: 48,
              borderRadius: "50%",
              border: "2px solid #fff",
              objectFit: "cover",
              objectPosition: "center",
              flexShrink: 0,
            }}
          />
        )}
        <div>
          <div
            style={{
              fontSize: 15,
              fontWeight: 700,
              color: T.textPrimary,
            }}
          >
            {person}
          </div>
          <div
            style={{
              fontSize: 13,
              color: T.textSecondary,
            }}
          >
            {title} → {company}
          </div>
        </div>
      </div>

      {/* Score Comparison Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 12,
          marginBottom: 20,
          marginTop: 16,
        }}
      >
        <div
          style={{
            background: "#ffffff",
            borderRadius: T.radiusMd,
            padding: "16px",
            textAlign: "center",
            boxShadow: T.shadowSm,
          }}
        >
          <div
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: T.textMuted,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: 4,
            }}
          >
            Before
          </div>
          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 36,
              fontWeight: 800,
              color: T.rose,
            }}
          >
            {beforeScore}
          </div>
        </div>

        <div
          style={{
            background: "#ffffff",
            borderRadius: T.radiusMd,
            padding: "16px",
            textAlign: "center",
            boxShadow: T.shadowSm,
            position: "relative",
          }}
        >
          <div
            style={{
              position: "absolute",
              top: -8,
              right: -8,
              width: 22,
              height: 22,
              background: completionBg,
              borderRadius: "50%",
              color: "#fff",
              fontSize: 11,
              fontWeight: 800,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            ✓
          </div>
          <div
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: T.textMuted,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: 4,
            }}
          >
            After
          </div>
          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 36,
              fontWeight: 800,
              color: scoreLabelColor,
            }}
          >
            {afterScore}
          </div>
        </div>
      </div>

      {/* Quote */}
      <div
        style={{
          fontSize: 13,
          color: T.textPrimary,
          lineHeight: 1.65,
          fontStyle: "italic",
          marginBottom: 8,
        }}
      >
        "{quote}"
      </div>

      {/* Outcome */}
      <div
        style={{
          fontSize: 11,
          fontWeight: 700,
          color: outcomeColor,
          marginTop: 8,
        }}
      >
        → {outcome}
      </div>
    </div>
  );
};
