from pathlib import Path
import tempfile, shutil, json, re
import local_qwen_project as m

checks=[]
def ck(name,cond,detail=''):
    if not cond: raise AssertionError(f'{name}: {detail}')
    checks.append(name)

ident=m._v36_release_identity()
ck('release identity',ident.get('version')=='V42.29.0',ident)
ck('engine identity',ident.get('engine')==m.V4229_ENGINE,ident)
ck('last mile limit includes eight-error checkpoint',m.V4229_ENDGAME_MAX_DIAGNOSTICS>=8,m.V4229_ENDGAME_MAX_DIAGNOSTICS)
ck('best state preservation advertised',ident.get('v4228_best_verified_state_promotion_preserved') is True)
ck('parser safety preserved',ident.get('v4227_parser_safe_changed_file_gate_preserved') is True)
ck('global compiler proof preserved',ident.get('v4226_global_compiler_proof_transaction_preserved') is True)

with tempfile.TemporaryDirectory(prefix='v4229_') as td:
    root=Path(td);(root/'src/components').mkdir(parents=True);(root/'src/hooks').mkdir(parents=True)
    (root/'src/components/DashboardView.tsx').write_text("export interface DashboardViewProps {\n  metrics: DashboardMetrics;\n}\nexport interface DashboardMetrics { total: number; }\nexport const DashboardView: React.FC<DashboardViewProps> = ({metrics}) => <div>{metrics.total}</div>;\n")
    (root/'src/components/InventoryView.tsx').write_text("export interface InventoryViewProps {\n  tools: Tool[];\n  categories: Category[];\n}\nexport const InventoryView: React.FC<InventoryViewProps> = () => <div/>;\n")
    (root/'src/components/CheckoutHistoryView.tsx').write_text("export interface CheckoutHistoryViewProps {\n  tools: Tool[];\n  persons: Person[];\n}\nexport const CheckoutHistoryView: React.FC<CheckoutHistoryViewProps> = () => <div/>;\n")
    (root/'src/hooks/useTools.ts').write_text("export const useTools = () => { const tools: Tool[] = []; return { tools }; };\n")
    (root/'src/hooks/useCategories.ts').write_text("export const useCategories = () => { const categories: Category[] = []; return { categories }; };\n")
    (root/'src/hooks/usePersons.ts').write_text("export const usePersons = () => { const persons: Person[] = []; return { persons }; };\n")
    (root/'src/hooks/useCheckouts.ts').write_text("export const useCheckouts = (tools: Tool[], _persons: Person[]) => { const checkouts: CheckoutRecord[] = []; return { checkouts }; };\n")
    (root/'src/hooks/useDashboardStats.ts').write_text("export interface DashboardMetrics { total: number; }\nexport const useDashboardStats = (tools: Tool[], checkouts: CheckoutRecord[], persons: Person[]): DashboardMetrics => ({ total: tools.length + checkouts.length + persons.length });\n")
    app="""import { InventoryView } from './components/InventoryView';
import { CheckoutHistoryView } from './components/CheckoutHistoryView';
import { DashboardView } from './components/DashboardView';
const NAVIGATION_ITEMS = [
  { id: 'dashboard', component: <DashboardView /> },
  { id: 'inventory', component: <InventoryView /> },
  { id: 'history', component: <CheckoutHistoryView /> },
];
export default function App() { return <main>{NAVIGATION_ITEMS.map(x => x.component)}</main>; }
"""
    (root/'src/App.tsx').write_text(app)
    err="""src/App.tsx(5,40): error TS2741: Property 'metrics' is missing in type '{}' but required in type 'DashboardViewProps'.
src/App.tsx(6,40): error TS2739: Type '{}' is missing the following properties from type 'InventoryViewProps': tools, categories
src/App.tsx(7,38): error TS2739: Type '{}' is missing the following properties from type 'CheckoutHistoryViewProps': tools, persons"""
    rows=m._v4222_parse_ts_diagnostics(root,err)
    out,reasons=m._v4229_try_react_prop_wiring(root,'src/App.tsx',app,rows)
    ck('react prop solver fired',bool(reasons),reasons)
    ck('dashboard metrics wired','<DashboardView metrics={metrics} />' in out,out)
    ck('inventory producers wired','<InventoryView tools={tools} categories={categories} />' in out,out)
    ck('history producers wired','<CheckoutHistoryView tools={tools} persons={persons} />' in out,out)
    ck('dependent checkout hook wired','const { checkouts } = useCheckouts(tools, persons);' in out,out)
    ck('dashboard hook wired last','const metrics = useDashboardStats(tools, checkouts, persons);' in out,out)
    app_pos=out.find('export default function App')
    ck('module jsx config moved into component scope',out.find('const NAVIGATION_ITEMS',app_pos)>app_pos,out)

    provider="""export const useApi = () => { const updateThing = async () => {}; const deleteThing = async () => {}; return { updateThing, deleteThing }; };"""
    consumer="""import { useApi } from './useApi';
export const useThings = () => { const { updateThingCommand, deleteThingCommand } = useApi(); return { updateThingCommand, deleteThingCommand }; };"""
    (root/'src/hooks/useApi.ts').write_text(provider);(root/'src/hooks/useThings.ts').write_text(consumer)
    er2="""src/hooks/useThings.ts(2,40): error TS2339: Property 'updateThingCommand' does not exist on type '{ updateThing: () => Promise<void>; deleteThing: () => Promise<void>; }'.
src/hooks/useThings.ts(2,60): error TS2339: Property 'deleteThingCommand' does not exist on type '{ updateThing: () => Promise<void>; deleteThing: () => Promise<void>; }'."""
    r2=m._v4222_parse_ts_diagnostics(root,er2)
    fixed,why=m._v4229_fix_provider_aliases(root,'src/hooks/useThings.ts',consumer,r2)
    ck('provider-source alias repair fired',len(why)==2,why)
    ck('update alias uses actual provider key','updateThing: updateThingCommand' in fixed,fixed)
    ck('delete alias uses actual provider key','deleteThing: deleteThingCommand' in fixed,fixed)

    csv='''interface CSVRow {\n  id: string;\n  name: string;\n  enabled: boolean;\n  note?: string;\n}\nconst csvContent = "id,name,enabled,note\\n";\nconst rows = source.map(item => ({ id: item.id, name: item.name, enabled: item.enabled ? "true" : "false", note: item.note || "" }));\nconst parseCSVLine = (line: string): CSVRow => {\n  const parsed: CSVRow[] = [];\n  parsed.push(parseField(line));\n  return parsed[0];\n};\nconst parseField = (field: string): Partial<CSVRow> => ({ id: field });\n'''
    (root/'src/hooks/useCSV.ts').write_text(csv)
    er3="""src/hooks/useCSV.ts(8,20): error TS2322: Types of property 'enabled' are incompatible. Type 'string' is not assignable to type 'boolean'.
src/hooks/useCSV.ts(11,15): error TS2345: Argument of type 'Partial<CSVRow>' is not assignable to parameter of type 'CSVRow'. Types of property 'name' are incompatible. Type 'string | undefined' is not assignable to type 'string'."""
    r3=m._v4222_parse_ts_diagnostics(root,er3)
    b,bwhy=m._v4229_fix_boolean_string_fields(csv,r3)
    ck('boolean string roundtrip removed','enabled: item.enabled' in b and '? "true"' not in b,b)
    c,cwhy=m._v4229_rewrite_typed_csv_parser(b,r3)
    ck('typed csv solver fired',bool(cwhy),cwhy)
    ck('typed csv parser validates column count','CSV row has too few columns' in c,c)
    ck('typed csv parser constructs boolean',"['true', '1', 'yes', 'y'].includes" in c,c)
    ck('dead partial field parser removed','parseField' not in c,c)

ck('no ts-ignore introduced','ts-ignore' not in out and 'ts-ignore' not in fixed and 'ts-ignore' not in c)
ck('bounded acceptance closure',1 <= m.V4229_MAX_CLOSURE_PASSES <= 4,m.V4229_MAX_CLOSURE_PASSES)
print(f'V42.29 regression: {len(checks)}/{len(checks)} PASS')
