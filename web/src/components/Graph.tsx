import { motion } from "framer-motion";
import { EDGES, NODES, type NodeId, type NodeMeta } from "../run";

const NODE_W = 150;
const NODE_H = 52;

const roleColor: Record<NodeMeta["role"], string> = {
  flow: "#2dd4bf",
  gate: "#fbbf24",
  write: "#fb7185",
  verify: "#a78bfa",
};

function center(n: NodeMeta) {
  return { cx: n.x + NODE_W / 2, cy: n.y + NODE_H / 2 };
}

function edgePath(fromId: NodeId, toId: NodeId) {
  const a = NODES.find((n) => n.id === fromId)!;
  const b = NODES.find((n) => n.id === toId)!;
  const { cx: ax, cy: ay } = center(a);
  const { cx: bx, cy: by } = center(b);
  const mx = (ax + bx) / 2;
  return `M ${ax} ${ay} C ${mx} ${ay}, ${mx} ${by}, ${bx} ${by}`;
}

interface Props {
  activeNode: NodeId | null;
  visited: Set<NodeId>;
  activeEdge: [NodeId, NodeId] | null;
}

export default function Graph({ activeNode, visited, activeEdge }: Props) {
  return (
    <svg
      viewBox="0 0 900 540"
      className="w-full h-auto"
      role="img"
      aria-label="Agent node graph"
    >
      <defs>
        <marker
          id="arrow"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#3a4c63" />
        </marker>
        <filter id="soft" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="4" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {EDGES.map((e, i) => {
        const isActive =
          activeEdge && activeEdge[0] === e.from && activeEdge[1] === e.to;
        return (
          <g key={i}>
            <path
              d={edgePath(e.from, e.to)}
              fill="none"
              stroke={isActive ? "#2dd4bf" : "#22303f"}
              strokeWidth={isActive ? 2.4 : 1.4}
              markerEnd="url(#arrow)"
              opacity={isActive ? 1 : 0.7}
            />
            {isActive && (
              <motion.circle
                r="3.6"
                fill="#7ff0e3"
                initial={{ offsetDistance: "0%" }}
                animate={{ offsetDistance: "100%" }}
                transition={{ duration: 0.9, ease: "easeInOut" }}
                style={{ offsetPath: `path("${edgePath(e.from, e.to)}")` } as never}
              />
            )}
          </g>
        );
      })}

      {NODES.map((n) => {
        const isActive = activeNode === n.id;
        const isVisited = visited.has(n.id);
        const color = roleColor[n.role];
        return (
          <g key={n.id} filter={isActive ? "url(#soft)" : undefined}>
            <motion.rect
              x={n.x}
              y={n.y}
              rx={12}
              width={NODE_W}
              height={NODE_H}
              fill={isActive ? "#12202b" : isVisited ? "#0f1823" : "#0b121b"}
              stroke={isActive || isVisited ? color : "#1e2a3a"}
              strokeWidth={isActive ? 2.2 : 1.2}
              animate={{
                scale: isActive ? 1.05 : 1,
                opacity: isVisited || isActive ? 1 : 0.55,
              }}
              transition={{ type: "spring", stiffness: 240, damping: 18 }}
              style={{ transformBox: "fill-box", transformOrigin: "center" }}
            />
            <text
              x={n.x + NODE_W / 2}
              y={n.y + NODE_H / 2 + 4}
              textAnchor="middle"
              fontFamily="'JetBrains Mono', monospace"
              fontSize="13"
              fill={isActive || isVisited ? "#e6edf3" : "#7c8ba0"}
            >
              {n.title}
            </text>
            {(n.role === "gate" || n.role === "write") && (
              <text
                x={n.x + NODE_W - 12}
                y={n.y + 16}
                textAnchor="end"
                fontSize="11"
                fill={color}
              >
                {n.role === "gate" ? "⏸ gate" : "⚡ write"}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
