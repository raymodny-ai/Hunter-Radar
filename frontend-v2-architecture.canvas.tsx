import {
  useHostTheme,
  useCanvasState,
  Stack,
  Row,
  H1,
  H2,
  H3,
  Text,
  Divider,
  Card,
  CardHeader,
  CardBody,
  Tag,
  Pill,
  Table,
  MetricsGrid,
  Callout,
  BarChart,
} from "qoder/canvas";

const ZONES: Array<{ id: string; name: string; color: string; count: number; items: string }> = [
  { id: "topnav", name: "TopNav", color: "blue", count: 6, items: "Logo, NavLinks, SearchBox, StatusLight, RightSidebarToggle, LogPanelToggle" },
  { id: "banners", name: "Banners", color: "green", count: 6, items: "EventTicker (8-K RAF marquee), Regime, DataStatus, Quota, PWA, FeatureFlag" },
  { id: "left", name: "LeftToolbar", color: "purple", count: 2, items: "AnalyzerLenses (OPT/SHT/DIV/INS), MobileBottomToolbar (md- drawer)" },
  { id: "main", name: "Main Canvas", color: "yellow", count: 7, items: "/, /screener, /detail/:symbol, /regime, /basket, /alerts, /admin" },
  { id: "right", name: "RightSidebar", color: "pink", count: 4, items: "Watchlist tab, Alerts tab, AI Copilot (LLM SSE), xl inline / md overlay drawer" },
];

const CHARTS: Array<[string, string, string]> = [
  ["Attribution Waterfall", "Detail", "bar+line"],
  ["4D Signal Radar", "Detail", "radar"],
  ["90-Day Trajectory", "Detail", "line+area"],
  ["Options Heatmap", "Detail", "heatmap"],
  ["Short Iceberg V2", "Detail", "bar+scatter"],
  ["Volume-Price Divergence", "Detail", "bar+line"],
  ["Insider Timeline", "Detail", "scatter"],
  ["Regime Timeline", "Regime", "timeline+bar"],
  ["BasketHistogram", "Basket", "bar"],
  ["SparkRadar", "Basket", "radar mini"],
];

const COMPONENTS: Array<[string, string, string]> = [
  ["Skeleton", "Chart / Table / Card", "Loading placeholder"],
  ["InfoTooltip", "Hover + Focus", "Compliance disclaimer"],
  ["AlertRuleForm", "RHF + Zod", "Alert rule CRUD"],
  ["FeatureFlagGate", "Conditional render", "Gray-release wrapper"],
  ["Disclaimer", "Red-tone tooltip", "Score disclaimer"],
  ["EventTicker", "RAF marquee", "8-K event ribbon"],
];

const INFRA: Array<[string, string, string]> = [
  ["State", "Zustand v4 (persist)", "UI store: sidebar, lenses, theme"],
  ["Data", "TanStack Query v5", "Server state + cache (staleTime)"],
  ["I18n", "i18next + zh-CN.json", "All UI text, no hardcoded Chinese"],
  ["Error", "Sentry + ErrorBoundary", "Crash reporting + fallback UI"],
  ["Perf", "PerformanceProbe", "FCP/LCP/CLS to /analytics/events"],
  ["Router", "TanStack Router", "Manual routeTree + file-based routes"],
  ["Charts", "ECharts 5 (tree-shake)", "hunter-dark theme + echarts.connect"],
  ["Push", "VAPID + ServiceWorker", "Web Push subscription"],
];

const BREAKPOINT_TABLE = [
  ["LeftToolbar", "Fixed left rail", "Fixed left rail", "Bottom floating bar"],
  ["RightSidebar", "Inline (flex)", "Overlay drawer + backdrop", "Hidden"],
  ["Main Canvas", "Center column", "Full width", "Full width, single col"],
  ["TopNav", "Full bar", "Full bar", "Collapsed + hamburger"],
  ["EventTicker", "Full width ribbon", "Full width ribbon", "Full width ribbon"],
];

const BREAKPOINTS: Array<{ name: string; width: string; layout: string; sidebar: string }> = [
  { name: "xl", width: "wide (1280+)", layout: "3-column: Left | Main | Right (inline)", sidebar: "Inline" },
  { name: "md", width: "medium (768-1280)", layout: "2-column: Main full-width, Right as overlay drawer", sidebar: "Overlay drawer" },
  { name: "mobile", width: "narrow (under 768)", layout: "Single column, Left as BottomToolbar", sidebar: "Hidden" },
];

export default function Architecture() {
  const { tokens } = useHostTheme();
  const [view, setView] = useCanvasState<string>("v2-view", "overview");

  const colorOf = (name: string): string => {
    if (name === "blue") return tokens.chart.blue;
    if (name === "green") return tokens.chart.green;
    if (name === "purple") return tokens.chart.purple;
    if (name === "yellow") return tokens.chart.goldenYellow;
    return tokens.chart.warmPink;
  };

  const accentBg = {
    background: tokens.bg.elevated,
    borderRadius: tokens.radius.md,
    padding: 12,
    border: `1px solid ${tokens.stroke.tertiary}`,
  };

  return (
    <Stack gap={16}>
      <H1>Hunter Radar V2.0 Architecture</H1>
      <Text tone="secondary" size="small">
        Frontend topology: 5 zones, 10 ECharts, 7 routes, 3 breakpoints. 58 FE tasks across 4 milestones.
      </Text>

      <MetricsGrid
        columns={5}
        items={[
          { label: "Routes", value: "7", tone: "info" },
          { label: "ECharts", value: "10", tone: "primary" },
          { label: "Components", value: "42+", tone: "success" },
          { label: "Files", value: "62", tone: "warning" },
          { label: "Lines", value: "~6.7K", tone: "danger" },
        ]}
      />

      <Row gap={8} align="center" wrap>
        <Text weight="semibold" size="small">View:</Text>
        <Tag active={view === "overview"} tone={view === "overview" ? "primary" : "neutral"} onClick={() => setView("overview")}>
          Layout Overview
        </Tag>
        <Tag active={view === "charts"} tone={view === "charts" ? "primary" : "neutral"} onClick={() => setView("charts")}>
          Chart Matrix
        </Tag>
        <Tag active={view === "components"} tone={view === "components" ? "primary" : "neutral"} onClick={() => setView("components")}>
          Components and Infra
        </Tag>
        <Tag active={view === "responsive"} tone={view === "responsive" ? "primary" : "neutral"} onClick={() => setView("responsive")}>
          Responsive
        </Tag>
      </Row>

      {view === "overview" && (
        <Stack gap={12}>
          <H2>Layout Topology</H2>
          <Callout type="info" title="5-zone Layout">
            Dark theme (#131722). Three-column on xl, overlay drawer on md, single column on mobile. Each zone has its own scroll isolation and Zustand-backed state.
          </Callout>
          <div style={accentBg}>
            <svg viewBox="0 0 800 460" style={{ width: "100%", maxWidth: 800 }}>
              <rect width={800} height={460} fill={tokens.bg.editor} rx={6} />

              <rect x={10} y={10} width={780} height={40} rx={4} fill={tokens.chart.blue} opacity={0.15} stroke={tokens.chart.blue} strokeWidth={1} />
              <text x={20} y={35} fill={tokens.chart.blue} fontSize={12} fontWeight={600}>TopNav</text>

              <rect x={10} y={56} width={780} height={28} rx={4} fill={tokens.chart.green} opacity={0.12} stroke={tokens.chart.green} strokeWidth={1} />
              <text x={20} y={75} fill={tokens.chart.green} fontSize={11} fontWeight={600}>Banners</text>

              <rect x={10} y={90} width={56} height={360} rx={4} fill={tokens.chart.purple} opacity={0.15} stroke={tokens.chart.purple} strokeWidth={1} />
              <text x={38} y={260} fill={tokens.chart.purple} fontSize={10} fontWeight={600} textAnchor="middle" transform="rotate(-90, 38, 260)">LeftToolbar</text>

              <rect x={72} y={90} width={500} height={360} rx={4} fill={tokens.chart.goldenYellow} opacity={0.08} stroke={tokens.chart.goldenYellow} strokeWidth={1} />
              <text x={82} y={110} fill={tokens.chart.goldenYellow} fontSize={12} fontWeight={600}>Main Canvas</text>

              <rect x={578} y={90} width={212} height={360} rx={4} fill={tokens.chart.warmPink} opacity={0.12} stroke={tokens.chart.warmPink} strokeWidth={1} />
              <text x={588} y={110} fill={tokens.chart.warmPink} fontSize={12} fontWeight={600}>RightSidebar</text>
            </svg>
          </div>

          <Stack gap={8}>
            {ZONES.map((z) => (
              <Card key={z.id} size="sm">
                <CardHeader title={
                  <Row gap={6} align="center">
                    <div style={{ width: 10, height: 10, borderRadius: 3, background: colorOf(z.color) }} />
                    <Text weight="semibold">{z.name}</Text>
                  </Row>
                } />
                <CardBody>
                  <Text size="small" tone="secondary">{z.items}</Text>
                </CardBody>
              </Card>
            ))}
          </Stack>
        </Stack>
      )}

      {view === "charts" && (
        <Stack gap={12}>
          <H2>ECharts Matrix (10 Charts)</H2>
          <BarChart
            categories={["Detail", "Regime", "Basket"]}
            series={[{ name: "Chart count", data: [7, 1, 2], tone: "primary" }]}
            height={160}
            valueFormatter={(v) => `${v}`}
          />
          <Table
            columns={[
              { key: "0", title: "Chart", width: "40%" },
              { key: "1", title: "Route Zone", width: "25%" },
              { key: "2", title: "Chart Type", width: "20%" },
              {
                key: "status",
                title: "Status",
                width: "15%",
                render: () => <Pill tone="success" size="sm">Done</Pill>,
              },
            ]}
            rows={CHARTS}
            rowKey="0"
            density="compact"
          />
        </Stack>
      )}

      {view === "components" && (
        <Stack gap={12}>
          <H2>Common Components</H2>
          <Callout type="info" title="UI Conventions">
            All text via i18next (no hardcoded Chinese). Radix UI primitives for popovers/dialogs. Tailwind CSS for layout. ECharts dispose() in useEffect cleanup.
          </Callout>
          <Table
            columns={[
              { key: "0", title: "Component", width: "25%" },
              { key: "1", title: "Variant / Pattern", width: "35%" },
              { key: "2", title: "Purpose", width: "40%" },
            ]}
            rows={COMPONENTS}
            rowKey="0"
            density="compact"
          />

          <Divider />

          <H2>Infrastructure Layer</H2>
          <Callout type="success" title="Performance & Quality">
            Vite 5 tree-shake reduces echarts to ~224KB gzip. TanStack Query staleTime per resource type. Playwright + axe-core covers E2E + WCAG AA on 3 viewports.
          </Callout>
          <Table
            columns={[
              { key: "0", title: "Layer", width: "15%" },
              { key: "1", title: "Technology", width: "35%" },
              { key: "2", title: "Role", width: "50%" },
            ]}
            rows={INFRA}
            rowKey="0"
            density="compact"
          />
        </Stack>
      )}

      {view === "responsive" && (
        <Stack gap={12}>
          <H2>Responsive Breakpoints</H2>
          <Callout type="warning" title="Mobile-first adaptation">
            BottomToolbar is a floating overlay that auto-collapses on scroll up. EventTicker remains full-width on all breakpoints for constant awareness of 8-K disclosures.
          </Callout>
          <Stack gap={8}>
            {BREAKPOINTS.map((b) => (
              <Card key={b.name} size="sm">
                <CardHeader
                  title={
                    <Row gap={6} align="center">
                      <Pill tone={b.name === "xl" ? "success" : b.name === "md" ? "warning" : "danger"} size="sm">{b.name}</Pill>
                      <Text weight="semibold" size="small">{b.width}</Text>
                    </Row>
                  }
                />
                <CardBody>
                  <Stack gap={3}>
                    <Text size="small" tone="secondary">{b.layout}</Text>
                    <Text size="small" tone="tertiary">Sidebar: {b.sidebar}</Text>
                  </Stack>
                </CardBody>
              </Card>
            ))}
          </Stack>

          <Divider />

          <H3>AppShell Breakpoint Behavior</H3>
          <Table
            columns={[
              { key: "element", title: "Element", width: "22%" },
              { key: "xl", title: "xl (wide)", width: "26%" },
              { key: "md", title: "md (medium)", width: "26%" },
              { key: "mobile", title: "mobile (narrow)", width: "26%" },
            ]}
            rows={BREAKPOINT_TABLE}
            rowKey="0"
            density="compact"
          />
        </Stack>
      )}
    </Stack>
  );
}