export default function QuickPicks({ onPick }) {
  const picks = [
    'Apple annual report 2023',
    'Tesla Q3 2023',
    'Microsoft presentation 2024',
    'Reliance Industries annual report 2023',
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
