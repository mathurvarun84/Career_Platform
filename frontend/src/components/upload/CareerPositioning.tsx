import type { PositioningResult } from "../../types/index";

interface CareerPositioningProps {
  positioning: PositioningResult;
  priorityFixes: string[];
}

export default function CareerPositioning({
  positioning,
  priorityFixes,
}: CareerPositioningProps) {
  return (
    <section className="mt-5 rounded-lg border-l-4 border-[#f9a825] bg-[#1a1a2e] p-4 text-left">
      <h3 className="mb-2 text-[20px] font-bold text-white">
        {positioning.positioning_line}
      </h3>
      <p className="mb-1.5 text-[14px] font-semibold text-[#f9a825]">
        {positioning.delta_line}
      </p>
      <p className="text-[13px] italic text-gray-400">{positioning.cta_line}</p>

      {priorityFixes.length > 0 ? (
        <>
          <h4 className="mb-2 mt-3 text-[14px] font-bold text-white">
            Top fixes to close the gap:
          </h4>
          <ol className="list-decimal pl-5">
            {priorityFixes.map((fix) => (
              <li key={fix} className="mb-1 text-[13px] text-[#f9a825]">
                {fix}
              </li>
            ))}
          </ol>
        </>
      ) : null}
    </section>
  );
}
