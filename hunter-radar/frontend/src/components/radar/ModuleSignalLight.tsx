interface ModuleSignalLightProps {
  name: string;
  value: number;          // 0–100
}

function pickLifecycle(v: number): "red" | "yellow" | "gray" | "green" {
  if (v >= 70) return "red";
  if (v >= 50) return "yellow";
  if (v >= 30) return "gray";
  return "green";
}

const colorMap = {
  red: "bg-hunter-red signal-red",
  yellow: "bg-hunter-yellow signal-yellow",
  gray: "bg-hunter-gray signal-gray",
  green: "bg-hunter-green signal-green",
};

export function ModuleSignalLight({ name, value }: ModuleSignalLightProps) {
  const lc = pickLifecycle(value);
  return (
    <div className="flex flex-col items-center gap-2">
      <div
        className={`w-12 h-12 rounded-full ${colorMap[lc]} transition-all`}
        title={`${name}: ${value.toFixed(0)}`}
      />
      <div className="text-xs text-slate-400">{name}</div>
      <div className="text-sm font-mono font-bold">{value.toFixed(0)}</div>
    </div>
  );
}
