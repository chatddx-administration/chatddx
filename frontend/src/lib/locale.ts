export type Catalog = { tag: string; messages: Record<string, string | string[]> };
type Given = Record<string, string | number>;
type Coded = { code: string; message: string; wording: string | string[] | null; params: Given };

const PLACEHOLDER = /%(?:\((\w+)\)s|%)/g;
// Policy: a parameter named so holds a language's tag, and one named languages tags
// separated by ", ", each said by its name, as the server says them.
const LANGUAGE_PARAMS = ["language", "into"];
// Policy: a parameter named so holds names separated by ", ", said as a list, as the server says it.
const LISTED_PARAMS = ["slots", "inserts", "worked"];
let spoken: Catalog | undefined;

export function speaking(given: Catalog): void {
  spoken = given;
}

export function t(message: string, given: Given = {}): string {
  return filled(translation(message), given);
}

// Policy: a message holding markup is markup, as a translation is trusted as the server's are;
// what is put into it is escaped, as a {% trans %} block's variables are.
export function th(message: string, given: Given = {}): string {
  return filled(translation(message), given, escaped);
}

export function tn(singular: string, plural: string, n: number, given: Given = {}): string {
  return filled(counted(singular, plural, n), given);
}

export function tp(context: string, message: string, given: Given = {}): string {
  return filled(translation(message, context), given);
}

export function tnp(context: string, singular: string, plural: string, n: number, given: Given = {}): string {
  return filled(counted(singular, plural, n, context), given);
}

// Policy: a message is said in its case where it is said in the running text, and raised to start a heading, a
// label or a sentence, as the server's upfirst raises it.
export function upFirst(said: string): string {
  return said.slice(0, 1).toUpperCase() + said.slice(1);
}

export function whoops(message: string): string {
  return translation(message, "whoops");
}

export function localized(coded: Coded): string {
  return coded.wording === null ? coded.message : worded(coded.code, coded.message, coded.wording, coded.params);
}

export function refusal(detail: string, wording: string | string[], params: Given): string {
  return worded("refusal", detail, wording, params);
}

// Accommodating for JavaScript, which writes some numbers other than Python does: what the
// page's catalog doesn't hold is said as the server wrote it, but for the languages it
// names and the lists it holds, which the server writes by their tags and joined by ", ".
function worded(context: string, written: string, wording: string | string[], params: Given): string {
  const [singular, plural] = typeof wording === "string" ? [wording] : wording;
  const named = said(params);
  if (singular === undefined) return written;
  if (!(keyed(singular, context) in catalog().messages) && named === params) return written;
  return plural === undefined
    ? tp(context, singular, named)
    : tnp(context, singular, plural, Number(params.num), named);
}

export function displayLanguage(tag: string): string {
  try {
    return new Intl.DisplayNames([catalog().tag], { type: "language", languageDisplay: "standard" }).of(tag) ?? tag;
  } catch {
    return tag;
  }
}

function said(params: Given): Given {
  const keys = Object.keys(params).filter(
    (k) => k === "languages" || LANGUAGE_PARAMS.includes(k) || LISTED_PARAMS.includes(k),
  );
  if (keys.length === 0) return params;
  const found = { ...params };
  for (const key of keys) {
    const value = found[key];
    if (typeof value !== "string") continue;
    if (key === "languages") found[key] = displayList(value.split(", ").map(displayLanguage));
    else if (LISTED_PARAMS.includes(key)) found[key] = displayList(value.split(", "));
    else found[key] = displayLanguage(value);
  }
  return found;
}

export function displayList(items: string[], type: "conjunction" | "disjunction" = "conjunction"): string {
  return new Intl.ListFormat(catalog().tag, { type }).format(items);
}

function translation(message: string, context?: string): string {
  const found = catalog().messages[keyed(message, context)];
  return typeof found === "string" ? found : message;
}

function counted(singular: string, plural: string, n: number, context?: string): string {
  const { tag, messages } = catalog();
  const found = messages[keyed(singular, context)];
  const [one, other] = Array.isArray(found) ? found : [singular, plural];
  return (new Intl.PluralRules(tag).select(n) === "one" ? one : other) ?? plural;
}

function keyed(message: string, context: string | undefined): string {
  return context === undefined ? message : `${context}\u0004${message}`;
}

function catalog(): Catalog {
  spoken ??= inPage() ?? { tag: "en", messages: {} };
  return spoken;
}

function inPage(): Catalog | undefined {
  const text = typeof document === "undefined" ? null : document.getElementById("locale")?.textContent;
  return text ? (JSON.parse(text) as Catalog) : undefined;
}

function filled(message: string, given: Given, shown: (value: string) => string = String): string {
  return message.replace(PLACEHOLDER, (_, name: string | undefined) => {
    if (name === undefined) return "%";
    const value = given[name];
    if (value === undefined) throw new Error(`nothing given for %(${name})s in ${JSON.stringify(message)}`);
    return shown(String(value));
  });
}

function escaped(value: string): string {
  return value.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}
