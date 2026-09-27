export function termLabel(term: string) {
  const [year, ...rest] = term.split("-");
  return `${rest.join(" ").replace(/^\w/, (letter) => letter.toUpperCase())} · ${year}`;
}
