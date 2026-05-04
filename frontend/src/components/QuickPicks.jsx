export default function QuickPicks({ onPick }) {
  const picks = [
    'Apple annual report 2024',
    'Turkish Airlines annual report 2024',
    'Infosys annual report 2024',
    'Samsung annual report 2024',
  ];

  return (
    <div className="quick-picks">
      <div className="quick-picks-label">Quick Picks</div>
      <div className="quick-pick-chips">
        {picks.map((pick, index) => (
          <button
            key={index}
            className="quick-pick-chip"
            onClick={() => onPick(pick)}
          >
            {pick}
          </button>
        ))}
      </div>
    </div>
  );
}
