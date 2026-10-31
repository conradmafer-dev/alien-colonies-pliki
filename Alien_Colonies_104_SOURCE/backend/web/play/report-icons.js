import {reportIconKind} from './fleet-motion.js?v=103';
const paths={
  "ranking": '<path d="m12 2 7 6-2 11-5 3-5-3L5 8l7-6ZM5 8h14M12 2l-3 6 3 14 3-14-3-6Z"/>',
  "expedition": '<circle cx="12" cy="12" r="9"/><path d="m16 8-2 6-6 2 2-6 6-2Z"/>',
  "scout": "<circle cx=\"11\" cy=\"11\" r=\"7\"/><path d=\"m16 16 5 5M11 7v4l3-3\"/>",
  "battle": "<path d=\"m3 3 8 5 10 13-4-1L6 9 3 3Zm18 0-8 5M18 9l-7 8M3 21l4-1M4 16l4 4M16 20l4-4\"/>",
  "warning": "<path d=\"m12 3 10 18H2L12 3ZM12 9v5M12 18h.01\"/>",
  "transport": "<path d=\"m3 7 8-4 8 4-8 4-8-4ZM3 7v10l8 4V11M11 21l4-2M18 11v9m-3-3 3 3 3-3\"/>",
  "return": "<path d=\"M9 5H4v5M4 5l6 6M6 16a8 8 0 1 0 2-12\"/><path d=\"m9 16 3-3 3 3v5H9v-5Z\"/>",
  "colonization": "<circle cx=\"10\" cy=\"14\" r=\"7\"/><path d=\"M14 14V2l7 3-7 3M4 12l5 2 2 6\"/>",
  "research": "<path d=\"M9 3h6M10 3v6L4 19a1.3 1.3 0 0 0 1.1 2h13.8a1.3 1.3 0 0 0 1.1-2L14 9V3M8 14h8\"/>",
  "construction": "<path d=\"M3 21h18M5 21V9l7-5 7 5v12M9 21v-6h6v6M9 10h.01M15 10h.01\"/>",
  "defense": "<path d=\"m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3ZM8 12l3 3 5-6\"/>",
  "shipyard": "<path d=\"m12 3 7 14-7-3-7 3 7-14ZM12 14v7M8 20l-2 1M16 20l2 1\"/>",
  "skill": "<path d=\"m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3l-5.6 2.9 1.1-6.2L3 9.6l6.2-.9L12 3Z\"/>",
  "protection": "<path d=\"m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6l8-4ZM9 11V8a3 3 0 0 1 6 0v3M8 11h8v6H8v-6Z\"/>",
  "empire": "<path d=\"M4 20h16M4 17 2 5l6 5 4-7 4 7 6-5-2 12H4Z\"/>",
  "recycling": "<path d=\"m8 5 4-3 4 7M12 2l-4 7M20 11l2 5-8 1M22 16l-4-7M12 21H6l1-8M6 21l-4-7\"/>"
};
export function reportTypeIcon(report, size=40) {
 const kind=reportIconKind(report);
 return `<svg class="report-type-icon ${kind}" data-report-kind="${kind}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[kind]}</svg>`;
}

