export const courseCodePattern = /^[A-Z]{3,10}\d{3,4}[A-Z]?$/;

export function isCourseCode(value: string): boolean {
  return courseCodePattern.test(value);
}
