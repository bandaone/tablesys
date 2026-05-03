const LOWER_WORDS = new Set(['and', 'of', 'for', 'in', 'the', 'to']);

const normalizeWhitespace = (value: string | null | undefined): string =>
  String(value || '').trim().replace(/\s+/g, ' ');

const smartTitleToken = (token: string): string => {
  const cleaned = token.trim();
  if (!cleaned) return '';
  if (/^[A-Z0-9]{2,10}$/.test(cleaned)) return cleaned;
  if (/^[A-Z]{2,10}[0-9]{1,4}$/.test(cleaned)) return cleaned;
  const lower = cleaned.toLowerCase();
  if (LOWER_WORDS.has(lower)) return lower;
  return lower.charAt(0).toUpperCase() + lower.slice(1);
};

const smartTitle = (value: string): string =>
  normalizeWhitespace(value)
    .split(/(\s+)/)
    .map((part, index) => {
      if (!part || /^\s+$/.test(part)) return part;
      const token = smartTitleToken(part);
      if (index === 0 && LOWER_WORDS.has(token)) {
        return token.charAt(0).toUpperCase() + token.slice(1);
      }
      return token;
    })
    .join('')
    .trim();

export const formatDepartmentName = (value?: string | null): string => {
  const normalized = normalizeWhitespace(value).replace(/[_-]+/g, ' ');
  if (!normalized) return '';
  return smartTitle(normalized);
};

export const formatPersonName = (value?: string | null): string => {
  const normalized = normalizeWhitespace(value);
  if (!normalized) return '';
  return smartTitle(normalized);
};

export const formatRoomName = (value?: string | null): string => {
  const normalized = normalizeWhitespace(value);
  if (!normalized) return '';
  if (/^[A-Za-z]{1,6}-?[0-9]{0,4}$/.test(normalized) || /^[A-Za-z]{2,10}[0-9]{0,4}$/.test(normalized)) {
    return normalized.toUpperCase();
  }
  return smartTitle(normalized.replace(/_/g, ' '));
};

export const formatGroupName = (rawName?: string | null, displayCode?: string | null): string => {
  const raw = normalizeWhitespace(rawName);
  if (!raw) return normalizeWhitespace(displayCode).toUpperCase();

  const normalized = raw.replace(/_/g, ' ').replace(/\s*-\s*/g, '-');
  const codeFirst = normalized.match(/^([A-Za-z]{2,10})[-\s]*(?:(?:yr|year|y)\s*)?([1-9])(?:[-\s]+(.+))?$/i);
  if (codeFirst) {
    const [, code, level, tail = ''] = codeFirst;
    const suffix = smartTitle(tail);
    return `${code.toUpperCase()} Year ${level}${suffix ? ` ${suffix}` : ''}`;
  }

  const suffixYear = normalized.match(/^(.+?)\s+(?:yr|year|y)\s*([1-9])(\b.*)?$/i);
  if (suffixYear) {
    const [, prefix, level, tail = ''] = suffixYear;
    const formattedTail = smartTitle(tail);
    return `${smartTitle(prefix)} Year ${level}${formattedTail ? ` ${formattedTail}` : ''}`;
  }

  return smartTitle(normalized.replace(/-/g, ' '));
};

export const formatGroupLabel = (group: { name?: string | null; display_code?: string | null }, preferCode = false): string => {
  const displayCode = normalizeWhitespace(group.display_code);
  if (preferCode && displayCode) {
    return displayCode.toUpperCase();
  }
  return formatGroupName(group.name, displayCode) || displayCode.toUpperCase();
};
