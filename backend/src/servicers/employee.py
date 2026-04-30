"""Servicers for NewHire.work.

UserServicer.hire_employee and EmployeeServicer.expand_skill /
run_task call Claude (via the Anthropic SDK) for the actual
LLM work. If `ANTHROPIC_API_KEY` is not set, a deterministic
mock is used so the demo still runs end-to-end.
"""

import json
import os
import random
import secrets
from typing import Any

from reboot.aio.contexts import (
    ReaderContext,
    TransactionContext,
    WriterContext,
)

from newhire.v1.employee import Skill, Task
from newhire.v1.employee_rbt import Employee, User


# =====================================================================
# Anthropic helper
# =====================================================================


_ANTHROPIC_MODEL = "claude-sonnet-4-5"


def _anthropic_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _call_claude_json(system: str, user: str) -> dict[str, Any]:
    """Call Claude with a system+user prompt; expect JSON back.

    Falls back to {} if the API key isn't present or anything
    fails — the caller supplies a mock instead.
    """
    if not _anthropic_available():
        return {}
    try:
        from anthropic import Anthropic
        client = Anthropic()
        msg = client.messages.create(
            model=_ANTHROPIC_MODEL,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(
            getattr(b, "text", "") for b in msg.content
            if getattr(b, "type", "") == "text"
        ).strip()
        # Strip markdown code fences if present.
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(
                line for line in lines
                if not line.strip().startswith("```")
            )
        return json.loads(text)
    except Exception as e:  # noqa: BLE001 — defensive for demo
        print(f"[NewHire] Claude call failed: {e!r}; using mock.")
        return {}


def _call_claude_text(system: str, user: str) -> str:
    """Call Claude and return raw markdown text. Empty on failure."""
    if not _anthropic_available():
        return ""
    try:
        from anthropic import Anthropic
        client = Anthropic()
        msg = client.messages.create(
            model=_ANTHROPIC_MODEL,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(
            getattr(b, "text", "") for b in msg.content
            if getattr(b, "type", "") == "text"
        ).strip()
    except Exception as e:  # noqa: BLE001
        print(f"[NewHire] Claude call failed: {e!r}; using mock.")
        return ""


# =====================================================================
# Name + avatar helpers
# =====================================================================


_FIRST_NAMES = [
    "Alex", "Jordan", "Sam", "Morgan", "Riley", "Casey", "Avery",
    "Quinn", "Drew", "Reese", "Skyler", "Sage", "Rowan", "Emery",
    "Hayden", "Parker", "Blake", "Cameron", "Logan", "Taylor",
    "Devon", "Eden", "Finley", "Harper", "Jules", "Kai", "Lennon",
    "Marlowe", "Noa", "Oakley", "Phoenix", "River", "Shiloh",
]
_LAST_NAMES = [
    "Chen", "Patel", "Garcia", "Kim", "Nguyen", "Silva", "Okafor",
    "Walsh", "Ivanov", "Müller", "Rossi", "Tanaka", "Andersson",
    "Dubois", "Khan", "Singh", "Martinez", "Johansson", "Reyes",
    "Hassan", "Costa", "Lindqvist", "Yamamoto", "Park", "Petrov",
]


def _generate_name() -> str:
    return f"{random.choice(_FIRST_NAMES)} {random.choice(_LAST_NAMES)}"


def _generate_avatar_seed() -> str:
    return secrets.token_hex(8)


# =====================================================================
# Mock fallbacks
# =====================================================================


def _mock_employee_profile(jd: str) -> dict[str, Any]:
    """Hand-tuned fallback when Claude is unavailable."""
    jd_lower = jd.lower()
    if "game" in jd_lower:
        return {
            "role": "Senior Game Designer",
            "skills": [
                {"name": "Systems Design", "description": "Designs core game loops and progression systems"},
                {"name": "Level Design", "description": "Crafts compelling level geometry and pacing"},
                {"name": "Player Experience", "description": "Tunes feel, feedback, and emotional arcs"},
                {"name": "Narrative Design", "description": "Weaves story into mechanics and environments"},
            ],
        }
    if "market" in jd_lower:
        return {
            "role": "Marketing Manager",
            "skills": [
                {"name": "Brand Strategy", "description": "Defines positioning, voice, and audience"},
                {"name": "Campaign Execution", "description": "Plans and ships multi-channel campaigns"},
                {"name": "Content Production", "description": "Writes and oversees on-brand assets"},
                {"name": "Analytics & Attribution", "description": "Measures impact and optimizes spend"},
            ],
        }
    if "engineer" in jd_lower or "developer" in jd_lower:
        return {
            "role": "Full-Stack Engineer",
            "skills": [
                {"name": "Frontend Architecture", "description": "Designs scalable React component systems"},
                {"name": "Backend Services", "description": "Builds reliable APIs and data pipelines"},
                {"name": "Systems Reliability", "description": "Handles deploys, monitoring, and on-call"},
                {"name": "Code Review", "description": "Raises code quality across the team"},
            ],
        }
    return {
        "role": "Generalist Operator",
        "skills": [
            {"name": "Discovery", "description": "Investigates problems and surfaces insights"},
            {"name": "Execution", "description": "Ships concrete work against deadlines"},
            {"name": "Communication", "description": "Aligns stakeholders with clear writing"},
        ],
    }


def _mock_skill_tasks(skill_name: str) -> list[dict[str, Any]]:
    return [
        {
            "name": f"Audit existing {skill_name.lower()} work",
            "description": f"Review current state of {skill_name.lower()} and identify gaps.",
            "atomic": True,
        },
        {
            "name": f"Draft a {skill_name.lower()} plan",
            "description": "Produce a one-page plan with goals, scope, and success metrics.",
            "atomic": True,
        },
        {
            "name": f"Execute first {skill_name.lower()} milestone",
            "description": "Ship the smallest meaningful artifact to learn from.",
            "atomic": True,
        },
    ]


# =====================================================================
# User servicer
# =====================================================================


class UserServicer(User.Servicer):

    async def hire_employee(
        self,
        context: TransactionContext,
        request: User.HireEmployeeRequest,
    ) -> User.HireEmployeeResponse:
        """Generate an Employee profile from a job description."""
        jd = request.job_description.strip()

        # Ask Claude for role + skill list. Fall back to mock.
        system = (
            "You are a workforce architect. Given a job description, "
            "output a JSON object with this exact shape:\n"
            "{\n"
            '  "role": "<short specific role title, e.g. \'Senior Backend Engineer\'>",\n'
            '  "skills": [\n'
            '    {"name": "<2-4 words, Title Case>", "description": "<one sentence, present tense>"},\n'
            "    ... 3 to 6 entries ...\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- Skills are ABILITIES, not deliverables ('Systems Design', not 'Design the combat system').\n"
            "- 3-6 skills total.\n"
            "- The role should be specific and realistic.\n"
            "- Output ONLY the JSON object — no prose, no markdown fences."
        )
        result = _call_claude_json(system, f"Job description:\n\n{jd}")
        if not result or "skills" not in result or "role" not in result:
            result = _mock_employee_profile(jd)

        role = str(result.get("role", "Generalist Operator"))
        raw_skills = result.get("skills", [])
        skills: list[Skill] = []
        for s in raw_skills:
            skills.append(Skill(
                name=str(s.get("name", "")),
                description=str(s.get("description", "")),
                expanded=False,
                tasks=[],
            ))

        name = _generate_name()
        avatar_seed = _generate_avatar_seed()

        # Factory create — pass fields as kwargs (Gotcha #9), NOT
        # wrapped in a Request object.
        employee, _ = await Employee.create(
            context,
            name=name,
            role=role,
            avatar_seed=avatar_seed,
            job_description=jd,
            skills=skills,
        )

        # Track on the User so list_my_employees works.
        self.state.employee_ids.append(employee.state_id)

        return User.HireEmployeeResponse(
            employee_id=employee.state_id,
            name=name,
            role=role,
        )

    async def list_my_employees(
        self,
        context: ReaderContext,
    ) -> User.ListMyEmployeesResponse:
        return User.ListMyEmployeesResponse(
            employee_ids=list(self.state.employee_ids),
        )


# =====================================================================
# Employee servicer
# =====================================================================


class EmployeeServicer(Employee.Servicer):

    async def create(
        self,
        context: WriterContext,
        request: Employee.CreateRequest,
    ) -> None:
        self.state.name = request.name
        self.state.role = request.role
        self.state.avatar_seed = request.avatar_seed
        self.state.job_description = request.job_description
        # Lists must be assigned, not extended via Field default.
        self.state.skills = list(request.skills)

    async def get(
        self,
        context: ReaderContext,
    ) -> Employee.GetResponse:
        return Employee.GetResponse(
            name=self.state.name,
            role=self.state.role,
            avatar_seed=self.state.avatar_seed,
            skills=list(self.state.skills),
        )

    async def expand_skill(
        self,
        context: WriterContext,
        request: Employee.ExpandSkillRequest,
    ) -> None:
        idx = request.skill_index
        if idx < 0 or idx >= len(self.state.skills):
            raise ValueError(
                f"skill_index {idx} out of range "
                f"(have {len(self.state.skills)} skills)"
            )
        skill = self.state.skills[idx]

        system = (
            "You decompose a skill into 2-4 concrete tasks an "
            "employee with this skill would actually perform. "
            "Output ONLY a JSON object with this shape:\n"
            "{\n"
            '  "tasks": [\n'
            '    {"name": "<short imperative task name>", '
            '"description": "<one sentence>", "atomic": true},\n'
            "    ...\n"
            "  ]\n"
            "}\n\n"
            "A task is ATOMIC if a single agent could complete it "
            "in one focused session given a clear scope of work. "
            "Bias toward atomic. No markdown fences."
        )
        user_msg = (
            f"Employee role: {self.state.role}\n"
            f"Skill: {skill.name}\n"
            f"Skill description: {skill.description}\n"
        )
        result = _call_claude_json(system, user_msg)
        raw_tasks = result.get("tasks") if result else None
        if not raw_tasks:
            raw_tasks = _mock_skill_tasks(skill.name)

        tasks: list[Task] = []
        for t in raw_tasks:
            tasks.append(Task(
                name=str(t.get("name", "")),
                description=str(t.get("description", "")),
                atomic=bool(t.get("atomic", True)),
                status="",
            ))

        # Mutate the skill in place by rebuilding the list — Reboot
        # state lists must be reassigned to register the change.
        new_skills = list(self.state.skills)
        new_skills[idx] = Skill(
            name=skill.name,
            description=skill.description,
            expanded=True,
            tasks=tasks,
        )
        self.state.skills = new_skills

    async def run_task(
        self,
        context: WriterContext,
        request: Employee.RunTaskRequest,
    ) -> Employee.RunTaskResponse:
        s_idx = request.skill_index
        t_idx = request.task_index
        if s_idx < 0 or s_idx >= len(self.state.skills):
            raise ValueError(f"skill_index {s_idx} out of range")
        skill = self.state.skills[s_idx]
        if t_idx < 0 or t_idx >= len(skill.tasks):
            raise ValueError(f"task_index {t_idx} out of range")
        task = skill.tasks[t_idx]

        system = (
            f"You are a {self.state.role} executing the task: "
            f"'{task.name}'. The user will give you a scope of "
            "work. Respond as if you are actively executing the "
            "task. Structure: (1) one-sentence acknowledgment, "
            "(2) a 'Plan' section with 3-5 bullet steps, "
            "(3) simulated execution narrating progress with "
            "'### Step N: ...' markdown headers, "
            "(4) a 'Deliverable' section with the actual output "
            "(draft, list, spec — whatever the task calls for). "
            "Be specific and concrete."
        )
        user_msg = (
            f"Task: {task.name}\n"
            f"Description: {task.description}\n"
            f"Parent skill: {skill.name}\n\n"
            f"Scope of work from user:\n{request.scope_of_work}"
        )
        output = _call_claude_text(system, user_msg)
        if not output:
            output = (
                f"### Acknowledged\n\nWorking on **{task.name}** "
                f"with scope: {request.scope_of_work}\n\n"
                f"### Plan\n- Investigate context\n- Draft output\n"
                f"- Iterate\n\n### Deliverable\n*(Mock output — "
                f"set ANTHROPIC_API_KEY for real LLM execution.)*"
            )

        # Mark the task as complete.
        new_tasks = list(skill.tasks)
        new_tasks[t_idx] = Task(
            name=task.name,
            description=task.description,
            atomic=task.atomic,
            status="complete",
        )
        new_skills = list(self.state.skills)
        new_skills[s_idx] = Skill(
            name=skill.name,
            description=skill.description,
            expanded=skill.expanded,
            tasks=new_tasks,
        )
        self.state.skills = new_skills

        return Employee.RunTaskResponse(output=output)
