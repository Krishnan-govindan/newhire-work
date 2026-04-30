/**
 * NewHire.work — Employee skill-tree canvas.
 *
 * Renders the employee at the center, skills branching out, and
 * tasks under expanded skills. Click a skill to decompose it
 * (calls Employee.expand_skill via Reboot). Click a task to open
 * a chat sheet where you provide a scope of work and the agent
 * "runs" it (Employee.run_task).
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FC,
} from "react";
import {
  ReactFlow,
  Background,
  Controls,
  type Edge,
  type Node,
  type NodeProps,
  Handle,
  Position,
  ReactFlowProvider,
  useReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "dagre";
import { motion, AnimatePresence } from "framer-motion";
import { createAvatar } from "@dicebear/core";
import { notionists } from "@dicebear/collection";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useEmployee } from "@api/newhire/v1/employee_rbt_react";
import css from "./App.module.css";

// --------------------------------------------------------------------
// Types
// --------------------------------------------------------------------

type Skill = {
  name: string;
  description: string;
  expanded: boolean;
  tasks: Task[];
};

type Task = {
  name: string;
  description: string;
  atomic: boolean;
  status: string;
};

type EmployeeNodeData = {
  kind: "employee";
  name: string;
  role: string;
  avatarSeed: string;
};

type SkillNodeData = {
  kind: "skill";
  index: number;
  name: string;
  description: string;
  expanded: boolean;
  loading: boolean;
  onExpand: (index: number) => void;
};

type TaskNodeData = {
  kind: "task";
  skillIndex: number;
  taskIndex: number;
  name: string;
  description: string;
  atomic: boolean;
  status: string;
  onOpen: (skillIndex: number, taskIndex: number) => void;
};

type FlowNode =
  | Node<EmployeeNodeData, "employee">
  | Node<SkillNodeData, "skill">
  | Node<TaskNodeData, "task">;

// --------------------------------------------------------------------
// Avatar helper (DiceBear, inline SVG data URI)
// --------------------------------------------------------------------

const avatarDataUri = (seed: string): string => {
  const avatar = createAvatar(notionists, {
    seed: seed || "default",
    backgroundColor: ["b6e3f4", "c0aede", "d1d4f9", "ffd5dc", "ffdfbf"],
  });
  return avatar.toDataUri();
};

// --------------------------------------------------------------------
// Custom node components
// --------------------------------------------------------------------

const EmployeeNode: FC<NodeProps<Node<EmployeeNodeData, "employee">>> = ({
  data,
}) => {
  return (
    <motion.div
      initial={{ scale: 0.6, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className={css.employeeCard}
    >
      <Handle
        type="source"
        position={Position.Bottom}
        className={css.handleHidden}
      />
      <img
        className={css.avatar}
        src={avatarDataUri(data.avatarSeed)}
        alt={data.name}
      />
      <div className={css.employeeName}>{data.name}</div>
      <div className={css.employeeRole}>{data.role}</div>
    </motion.div>
  );
};

const SkillNode: FC<NodeProps<Node<SkillNodeData, "skill">>> = ({ data }) => {
  return (
    <motion.div
      initial={{ scale: 0.7, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className={`${css.skillCard} ${data.expanded ? css.expanded : ""}`}
      onClick={() => !data.expanded && data.onExpand(data.index)}
      role="button"
    >
      <Handle
        type="target"
        position={Position.Top}
        className={css.handleHidden}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        className={css.handleHidden}
      />
      <div className={css.skillName}>{data.name}</div>
      <div className={css.skillDesc}>{data.description}</div>
      {data.loading && (
        <div className={css.loadingPill}>decomposing…</div>
      )}
      {!data.loading && !data.expanded && (
        <div className={css.expandHint}>click to break down</div>
      )}
    </motion.div>
  );
};

const TaskNode: FC<NodeProps<Node<TaskNodeData, "task">>> = ({ data }) => {
  const completed = data.status === "complete";
  return (
    <motion.div
      initial={{ scale: 0.7, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className={`${css.taskCard} ${
        data.atomic ? css.taskAtomic : css.taskComposite
      } ${completed ? css.taskComplete : ""}`}
      onClick={() => data.onOpen(data.skillIndex, data.taskIndex)}
      role="button"
    >
      <Handle
        type="target"
        position={Position.Top}
        className={css.handleHidden}
      />
      <div className={css.taskHeader}>
        <span className={css.taskDot} />
        <span className={css.taskName}>{data.name}</span>
      </div>
      <div className={css.taskDesc}>{data.description}</div>
      <div className={css.taskAction}>
        {completed ? "✓ complete" : data.atomic ? "▶ run task" : "↳ break down"}
      </div>
    </motion.div>
  );
};

const nodeTypes = {
  employee: EmployeeNode,
  skill: SkillNode,
  task: TaskNode,
};

// --------------------------------------------------------------------
// Layout via dagre
// --------------------------------------------------------------------

const NODE_WIDTHS = { employee: 260, skill: 220, task: 220 } as const;
const NODE_HEIGHTS = { employee: 200, skill: 110, task: 110 } as const;

const layoutNodes = (nodes: FlowNode[], edges: Edge[]): FlowNode[] => {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({
    rankdir: "TB",
    nodesep: 40,
    ranksep: 90,
    marginx: 30,
    marginy: 30,
  });

  nodes.forEach((n) => {
    const kind = (n.type ?? "skill") as keyof typeof NODE_WIDTHS;
    g.setNode(n.id, {
      width: NODE_WIDTHS[kind],
      height: NODE_HEIGHTS[kind],
    });
  });
  edges.forEach((e) => g.setEdge(e.source, e.target));
  dagre.layout(g);

  return nodes.map((n) => {
    const pos = g.node(n.id);
    const kind = (n.type ?? "skill") as keyof typeof NODE_WIDTHS;
    return {
      ...n,
      position: {
        x: pos.x - NODE_WIDTHS[kind] / 2,
        y: pos.y - NODE_HEIGHTS[kind] / 2,
      },
    };
  });
};

// --------------------------------------------------------------------
// Task Chat Sheet (slides from right)
// --------------------------------------------------------------------

type ChatSheetProps = {
  open: boolean;
  taskName: string;
  taskDescription: string;
  status: string;
  isRunning: boolean;
  output: string;
  onClose: () => void;
  onRun: (scope: string) => void;
};

const ChatSheet: FC<ChatSheetProps> = ({
  open,
  taskName,
  taskDescription,
  status,
  isRunning,
  output,
  onClose,
  onRun,
}) => {
  const [scope, setScope] = useState("");
  const outputRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className={css.sheetBackdrop}
            onClick={onClose}
          />
          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "tween", duration: 0.25 }}
            className={css.sheet}
          >
            <div className={css.sheetHeader}>
              <div>
                <div className={css.sheetTitle}>{taskName}</div>
                <div className={css.sheetSubtitle}>{taskDescription}</div>
              </div>
              <button
                onClick={onClose}
                className={css.sheetClose}
                aria-label="Close"
              >
                ×
              </button>
            </div>

            {!output && (
              <div className={css.sheetBody}>
                <label className={css.sheetLabel}>Scope of work</label>
                <textarea
                  className={css.sheetTextarea}
                  value={scope}
                  onChange={(e) => setScope(e.target.value)}
                  placeholder="e.g. Audience: indie devs. Tone: confident, plain. Length: 400 words. Include 3 examples."
                  rows={6}
                  disabled={isRunning}
                />
                <button
                  onClick={() => onRun(scope)}
                  disabled={!scope.trim() || isRunning}
                  className={css.sheetRunBtn}
                >
                  {isRunning ? "Running…" : "Run agent"}
                </button>
                <div className={css.sheetStatus}>status: {status || "idle"}</div>
              </div>
            )}

            {output && (
              <div className={css.sheetBody}>
                <div className={css.sheetLabel}>Agent output</div>
                <div className={css.sheetOutput} ref={outputRef}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {output}
                  </ReactMarkdown>
                </div>
              </div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

// --------------------------------------------------------------------
// Main canvas
// --------------------------------------------------------------------

type ShowProfileProps = {
  welcomeMessage?: string;
};

const SkillTreeCanvas: FC<ShowProfileProps> = ({ welcomeMessage }) => {
  const employee = useEmployee();
  const { response, isLoading } = employee.useGet();
  const { fitView } = useReactFlow();

  const [expandingSkill, setExpandingSkill] = useState<number | null>(null);
  const [activeTask, setActiveTask] = useState<{
    skillIndex: number;
    taskIndex: number;
  } | null>(null);
  const [taskOutput, setTaskOutput] = useState("");
  const [isRunning, setIsRunning] = useState(false);

  // ----------------- handlers -----------------

  const handleExpandSkill = useCallback(
    async (skillIndex: number) => {
      setExpandingSkill(skillIndex);
      try {
        await employee.expandSkill({ skillIndex });
      } finally {
        setExpandingSkill(null);
      }
    },
    [employee],
  );

  const handleOpenTask = useCallback(
    (skillIndex: number, taskIndex: number) => {
      setActiveTask({ skillIndex, taskIndex });
      setTaskOutput("");
    },
    [],
  );

  const handleRunTask = useCallback(
    async (scope: string) => {
      if (!activeTask) return;
      setIsRunning(true);
      try {
        const result = await employee.runTask({
          skillIndex: activeTask.skillIndex,
          taskIndex: activeTask.taskIndex,
          scopeOfWork: scope,
        });
        if ("response" in result && result.response) {
          setTaskOutput(result.response.output);
        } else {
          setTaskOutput(
            "_The agent encountered an error. Try again._",
          );
        }
      } finally {
        setIsRunning(false);
      }
    },
    [activeTask, employee],
  );

  // ----------------- node/edge derivation -----------------

  const skills: Skill[] = useMemo(
    () => (response?.skills ?? []) as Skill[],
    [response?.skills],
  );

  const { nodes, edges } = useMemo(() => {
    if (!response) return { nodes: [] as FlowNode[], edges: [] as Edge[] };

    const nodes: FlowNode[] = [];
    const edges: Edge[] = [];

    nodes.push({
      id: "employee",
      type: "employee",
      position: { x: 0, y: 0 },
      data: {
        kind: "employee",
        name: response.name,
        role: response.role,
        avatarSeed: response.avatarSeed,
      },
    });

    skills.forEach((skill, sIdx) => {
      const skillId = `skill-${sIdx}`;
      nodes.push({
        id: skillId,
        type: "skill",
        position: { x: 0, y: 0 },
        data: {
          kind: "skill",
          index: sIdx,
          name: skill.name,
          description: skill.description,
          expanded: skill.expanded,
          loading: expandingSkill === sIdx,
          onExpand: handleExpandSkill,
        },
      });
      edges.push({
        id: `e-emp-${skillId}`,
        source: "employee",
        target: skillId,
        animated: true,
        style: { stroke: "var(--color-purple)", strokeWidth: 2 },
      });

      if (skill.expanded && skill.tasks?.length) {
        skill.tasks.forEach((task, tIdx) => {
          const taskId = `task-${sIdx}-${tIdx}`;
          nodes.push({
            id: taskId,
            type: "task",
            position: { x: 0, y: 0 },
            data: {
              kind: "task",
              skillIndex: sIdx,
              taskIndex: tIdx,
              name: task.name,
              description: task.description,
              atomic: task.atomic,
              status: task.status,
              onOpen: handleOpenTask,
            },
          });
          edges.push({
            id: `e-${skillId}-${taskId}`,
            source: skillId,
            target: taskId,
            animated: false,
            style: {
              stroke: task.atomic ? "var(--color-green)" : "var(--color-orange)",
              strokeWidth: 1.5,
            },
          });
        });
      }
    });

    const laidOut = layoutNodes(nodes, edges);
    return { nodes: laidOut, edges };
  }, [response, skills, expandingSkill, handleExpandSkill, handleOpenTask]);

  // refit view when graph changes
  useEffect(() => {
    if (nodes.length > 0) {
      const t = setTimeout(() => fitView({ padding: 0.2, duration: 400 }), 50);
      return () => clearTimeout(t);
    }
  }, [nodes.length, fitView]);

  // ----------------- render -----------------

  if (isLoading && !response) {
    return (
      <div className={css.loadingScreen}>
        <div className={css.loadingPulse}>materializing employee…</div>
      </div>
    );
  }

  const activeTaskData =
    activeTask &&
    skills[activeTask.skillIndex]?.tasks?.[activeTask.taskIndex];

  return (
    <div className={css.root}>
      <header className={css.header}>
        <div className={css.headerLeft}>
          <div className={css.logo}>NewHire<span>.work</span></div>
          <div className={css.pitch}>Hire new employees under 10 seconds</div>
        </div>
        <div className={css.headerRight}>
          {welcomeMessage && (
            <div className={css.welcome}>{welcomeMessage}</div>
          )}
          <div className={css.headerStat}>
            <span className={css.statValue}>{skills.length}</span>
            <span className={css.statLabel}>skills</span>
          </div>
          <div className={css.headerStat}>
            <span className={css.statValue}>
              {skills.reduce((n, s) => n + (s.tasks?.length ?? 0), 0)}
            </span>
            <span className={css.statLabel}>tasks</span>
          </div>
        </div>
      </header>

      <div className={css.canvasWrap}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          minZoom={0.3}
          maxZoom={1.5}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnScroll
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={28} size={1.5} color="#2d2d4a" />
          <Controls
            showInteractive={false}
            position="bottom-right"
            className={css.flowControls}
          />
        </ReactFlow>
      </div>

      <ChatSheet
        open={activeTask !== null}
        taskName={activeTaskData?.name ?? ""}
        taskDescription={activeTaskData?.description ?? ""}
        status={activeTaskData?.status ?? "idle"}
        isRunning={isRunning}
        output={taskOutput}
        onClose={() => {
          setActiveTask(null);
          setTaskOutput("");
        }}
        onRun={handleRunTask}
      />
    </div>
  );
};

// --------------------------------------------------------------------
// Exported entry — wraps in ReactFlowProvider so useReactFlow works
// --------------------------------------------------------------------

export const ShowProfileApp: FC<ShowProfileProps> = (props) => {
  return (
    <ReactFlowProvider>
      <SkillTreeCanvas {...props} />
    </ReactFlowProvider>
  );
};
