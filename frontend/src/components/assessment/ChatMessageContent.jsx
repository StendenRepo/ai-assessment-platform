'use client';

// Order matters: links first, then bold/code/italic.
// Groups: 2=link text, 3=link url, 4=bold, 5=code, 6=italic.
const INLINE_PATTERN =
  /(\[([^\]]+)\]\(([^)\s]+)\)|\*\*(.+?)\*\*|`([^`]+)`|\*(.+?)\*)/g;

// Only allow safe schemes so AI-supplied text can't inject javascript: URLs.
function safeHref(url) {
  return /^(https?:|mailto:)/i.test(url) ? url : null;
}

function renderInline(text) {
  const parts = [];
  let lastIndex = 0;
  let match;
  let key = 0;

  INLINE_PATTERN.lastIndex = 0;
  while ((match = INLINE_PATTERN.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    if (match[2] && match[3]) {
      const href = safeHref(match[3]);
      parts.push(
        href ? (
          <a
            key={key++}
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary underline underline-offset-2 hover:text-primary/80 break-words"
          >
            {match[2]}
          </a>
        ) : (
          match[2]
        )
      );
    } else if (match[4]) {
      parts.push(
        <strong key={key++} className="font-semibold text-foreground">
          {match[4]}
        </strong>
      );
    } else if (match[5]) {
      parts.push(
        <code
          key={key++}
          className="rounded bg-background/80 px-1 py-0.5 font-mono text-[10px]"
        >
          {match[5]}
        </code>
      );
    } else if (match[6]) {
      parts.push(
        <em key={key++} className="italic">
          {match[6]}
        </em>
      );
    }
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length ? parts : text;
}

function listItemClass(type) {
  return type === 'ordered'
    ? 'list-decimal pl-4 space-y-1'
    : 'list-disc pl-4 space-y-1';
}

function renderListGroup(items, key, ordered) {
  const ListTag = ordered ? 'ol' : 'ul';
  return (
    <ListTag
      key={key}
      className={`text-xs ${listItemClass(ordered ? 'ordered' : 'bullet')}`}
    >
      {items.map((item, index) => (
        <li key={index} className="leading-relaxed">
          {renderInline(item.text)}
          {item.children?.length > 0 && (
            <ul className="mt-1 list-disc pl-4 space-y-0.5">
              {item.children.map((child, childIndex) => (
                <li
                  key={childIndex}
                  className="leading-relaxed text-muted-foreground"
                >
                  {renderInline(child)}
                </li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ListTag>
  );
}

function renderTextBlock(text, key) {
  const lines = text.split('\n');
  const nodes = [];
  let listBuffer = [];
  let listOrdered = false;
  let nodeKey = 0;

  function flushList() {
    if (!listBuffer.length) return;
    nodes.push(
      renderListGroup(listBuffer, `${key}-list-${nodeKey++}`, listOrdered)
    );
    listBuffer = [];
  }

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushList();
      continue;
    }

    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      flushList();
      const level = heading[1].length;
      nodes.push(
        <p
          key={`${key}-h-${nodeKey++}`}
          className={
            level <= 2
              ? 'text-xs font-semibold text-foreground'
              : 'text-xs font-medium text-foreground'
          }
        >
          {renderInline(heading[2])}
        </p>
      );
      continue;
    }

    const ordered = line.match(/^\d+\.\s+(.+)$/);
    const bullet = line.match(/^[-*]\s+(.+)$/);
    const subBullet = rawLine.match(/^\s+[-*]\s+(.+)$/);

    if (ordered) {
      if (listBuffer.length && !listOrdered) flushList();
      listOrdered = true;
      listBuffer.push({ text: ordered[1], children: [] });
      continue;
    }

    if (subBullet && listBuffer.length) {
      const parent = listBuffer[listBuffer.length - 1];
      parent.children = parent.children || [];
      parent.children.push(subBullet[1]);
      continue;
    }

    if (bullet) {
      if (listBuffer.length && listOrdered) flushList();
      listOrdered = false;
      listBuffer.push({ text: bullet[1], children: [] });
      continue;
    }

    flushList();
    nodes.push(
      <p key={`${key}-p-${nodeKey++}`} className="text-xs leading-relaxed">
        {renderInline(line)}
      </p>
    );
  }

  flushList();
  return nodes.length ? (
    <div key={key} className="space-y-2">
      {nodes}
    </div>
  ) : null;
}

function parseBlocks(content) {
  if (!content) return [];

  const blocks = [];
  const pattern = /```(\w*)\n?([\s\S]*?)```/g;
  let lastIndex = 0;
  let match;

  while ((match = pattern.exec(content)) !== null) {
    if (match.index > lastIndex) {
      const text = content.slice(lastIndex, match.index).trim();
      if (text) blocks.push({ type: 'text', text });
    }
    blocks.push({ type: 'code', text: match[2].trim() });
    lastIndex = match.index + match[0].length;
  }

  const tail = content.slice(lastIndex).trim();
  if (tail) blocks.push({ type: 'text', text: tail });

  return blocks;
}

export default function ChatMessageContent({ content }) {
  const blocks = parseBlocks(content);

  if (!blocks.length) {
    return <p className="text-xs leading-relaxed">{content}</p>;
  }

  return (
    <div className="space-y-2.5">
      {blocks.map((block, index) => {
        if (block.type === 'code') {
          return (
            <pre
              key={index}
              className="overflow-x-auto rounded-md border border-border bg-background/70 px-2.5 py-2 text-[10px] leading-relaxed text-muted-foreground whitespace-pre-wrap"
            >
              {block.text}
            </pre>
          );
        }
        return renderTextBlock(block.text, index);
      })}
    </div>
  );
}
