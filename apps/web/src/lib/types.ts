export type DataStatus = "LIVE" | "DELAYED" | "HISTORICAL" | "SIMULATED";
export type Verification = "VERIFIED" | "PROVISIONAL" | "UNVERIFIED" | "SIMULATED";
export type Timeframe = "1D" | "1W" | "1M";

export interface Session {
  user: { id: string; email: string; display_name: string };
  organization: { id: string; name: string; plan: string; entitlements: Record<string, number> };
  role: string;
}

export interface ProviderInfo {
  name: string;
  data_status: DataStatus;
  adjustment: string;
  license_note: string;
  timeframes: Timeframe[];
  can_enumerate_universe: boolean;
}

export interface SymbolInfo {
  symbol: string;
  name: string;
  exchange: string;
  asset_type: string;
  sector: string | null;
  industry: string | null;
}

export interface Provenance {
  symbol: string;
  provider: string;
  exchange: string;
  timeframe: Timeframe;
  timezone: string;
  adjustment: string;
  data_status: DataStatus;
  verification: Verification;
  last_bar_forming: boolean;
  complete: boolean;
  warnings: string[];
  first_bar: string | null;
  last_bar: string | null;
}

export interface Bar {
  t: number;
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
}

export interface BarsResponse extends Provenance {
  bars: Bar[];
}

export interface IndicatorParam {
  name: string;
  kind: "int" | "float" | "source";
  default: number | string;
  min: number | null;
  max: number | null;
  title: string;
}

export interface IndicatorSpec {
  id: string;
  name: string;
  category: string;
  overlay: boolean;
  version: string;
  reference: string;
  levels: number[];
  params: IndicatorParam[];
  outputs: { name: string; title: string; style: "line" | "histogram" | "dots" }[];
}

export interface IndicatorResult extends Provenance {
  t: number[];
  outputs: Record<string, (number | null)[]>;
}

export interface Watchlist {
  id: string;
  name: string;
  symbols: string[];
  created_at: string;
}

export interface Operand {
  value?: number;
  field?: "open" | "high" | "low" | "close" | "volume";
  indicator?: string;
  params?: Record<string, number | string>;
  output?: string;
  timeframe?: Timeframe;
  offset?: number;
  multiplier?: number;
}

export type Comparator = ">" | ">=" | "<" | "<=" | "crosses_above" | "crosses_below";

export interface Condition {
  left: Operand;
  op: Comparator;
  right: Operand;
}

export interface Group {
  logic: "and" | "or";
  rules: (Condition | Group)[];
}

export interface ScanDefinition {
  filter: Group;
  sort_by?: Operand;
  sort_desc?: boolean;
  limit?: number;
}

export interface Universe {
  type: "provider" | "symbols" | "watchlist";
  symbols?: string[];
  watchlist_id?: string;
  asset_types?: string[];
}

export interface ScanRow {
  symbol: string;
  name: string;
  sector: string | null;
  industry: string | null;
  asset_type: string;
  price: number | null;
  bar_date: string;
  values: Record<string, number | null>;
  sort_value: number | null;
  verification: Verification;
  data_status: DataStatus;
  warnings: string[];
}

export interface ScanResult {
  engine_version: string;
  provider: string;
  data_status: DataStatus;
  as_of: string;
  conditions: string[];
  columns: string[];
  scanned: number;
  matched: number;
  insufficient: string[];
  errors: { symbol: string; error: string }[];
  duration_ms: number;
  rows: ScanRow[];
}

export interface Preset {
  id: string;
  name: string;
  description: string;
  definition: ScanDefinition;
}

export interface SavedScan {
  id: string;
  name: string;
  definition: ScanDefinition;
  universe: Universe;
  updated_at: string;
}
