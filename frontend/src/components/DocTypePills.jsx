export default function DocTypePills({ selected, onChange }) {
  const docTypes = [
    { value: 'annual report', label: 'Annual Report' },
    { value: 'quarterly', label: 'Quarterly' },
    { value: 'presentation', label: 'Presentation' },
  ];

  return (
    <div className="doc-pills">
      {docTypes.map(({ value, label }) => (
        <button
          key={value}
          className={`doc-pill ${selected === value ? 'active' : ''}`}
          onClick={() => onChange(value)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
