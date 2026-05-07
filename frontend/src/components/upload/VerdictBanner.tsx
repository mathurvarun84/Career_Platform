interface VerdictBannerProps {
  atsScore: number;
  jdMatch: number | null;
  percentile: number | null;
}

export default function VerdictBanner({
  atsScore,
  jdMatch,
  percentile,
}: VerdictBannerProps) {
  void atsScore;
  void jdMatch;
  void percentile;

  return (
    <section className="text-center">
      <span className="mx-auto mb-4 block w-fit rounded-full border border-green-200 bg-green-50 px-3.5 py-1 text-[12px] font-semibold text-green-700">
        ● Analysis Complete
      </span>
      <h2 className="mb-1.5 text-center text-[24px] font-bold text-[#1a1a2e]">
        Your Resume Score
      </h2>
    </section>
  );
}
