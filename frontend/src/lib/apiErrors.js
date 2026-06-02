export function normalizeErrorDetail(detail) {
  if (!detail) return null;
  if (typeof detail === 'string') return detail;

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item.msg === 'string') return item.msg;
        return null;
      })
      .filter(Boolean);
    if (messages.length) return messages.join(', ');
    return null;
  }

  if (typeof detail === 'object' && typeof detail.msg === 'string') {
    return detail.msg;
  }

  return null;
}
