"""NewHire.work — virtual employee skill-tree API.

Built on Reboot. The AI (Claude / ChatGPT / etc.) talks to this
backend through MCP tools. The user pastes a job description in
chat → Claude calls `User.hire_employee(...)` → an Employee state
is created with a generated name, role, avatar, and a tree of
skills. The Employee's React UI renders the skill tree as an
interactive canvas inside the chat.
"""

from reboot.api import (
    API,
    UI,
    Field,
    Methods,
    Model,
    Reader,
    Tool,
    Transaction,
    Type,
    Writer,
)


# =====================================================================
# Helper Models — these are standalone (NOT nested on Employee) so
# servicers can import them directly. See Critical Gotcha #4.
# =====================================================================


class Task(Model):
    """A single concrete task underneath a skill."""
    name: str = Field(tag=1, default="")
    description: str = Field(tag=2, default="")
    # Proto3 zero defaults only — servicer sets these on create.
    atomic: bool = Field(tag=3, default=False)
    status: str = Field(tag=4, default="")  # "" | "running" | "complete"


class Skill(Model):
    """A capability of the employee. Decomposes into Tasks."""
    name: str = Field(tag=1, default="")
    description: str = Field(tag=2, default="")
    expanded: bool = Field(tag=3, default=False)
    tasks: list[Task] = Field(tag=4, default_factory=list)


# =====================================================================
# User — the MCP front door. Empty state; methods create Employees.
# =====================================================================


class UserState(Model):
    employee_ids: list[str] = Field(tag=1, default_factory=list)


class HireEmployeeRequest(Model):
    job_description: str = Field(tag=1)


class HireEmployeeResponse(Model):
    employee_id: str = Field(tag=1)
    name: str = Field(tag=2)
    role: str = Field(tag=3)


class ListEmployeesResponse(Model):
    employee_ids: list[str] = Field(tag=1, default_factory=list)


# =====================================================================
# Employee — the actual application state.
# =====================================================================


class EmployeeState(Model):
    name: str = Field(tag=1, default="")
    role: str = Field(tag=2, default="")
    avatar_seed: str = Field(tag=3, default="")
    job_description: str = Field(tag=4, default="")
    skills: list[Skill] = Field(tag=5, default_factory=list)


class CreateEmployeeRequest(Model):
    name: str = Field(tag=1)
    role: str = Field(tag=2)
    avatar_seed: str = Field(tag=3)
    job_description: str = Field(tag=4)
    skills: list[Skill] = Field(tag=5, default_factory=list)


class GetEmployeeResponse(Model):
    name: str = Field(tag=1)
    role: str = Field(tag=2)
    avatar_seed: str = Field(tag=3)
    skills: list[Skill] = Field(tag=4, default_factory=list)


class ExpandSkillRequest(Model):
    skill_index: int = Field(tag=1)


class RunTaskRequest(Model):
    skill_index: int = Field(tag=1)
    task_index: int = Field(tag=2)
    scope_of_work: str = Field(tag=3)


class RunTaskResponse(Model):
    output: str = Field(tag=1)


class ShowProfileConfig(Model):
    """Config the AI passes when opening the canvas UI."""
    welcome_message: str = Field(tag=1, default="")


# =====================================================================
# API surface
# =====================================================================


api = API(
    User=Type(
        state=UserState,
        methods=Methods(
            hire_employee=Transaction(
                request=HireEmployeeRequest,
                response=HireEmployeeResponse,
                description=(
                    "Hire a new virtual employee from a job "
                    "description. Generates a realistic name, "
                    "role title, avatar seed, and a tree of "
                    "3-6 top-level skills using Claude. Returns "
                    "the employee_id — pass it to "
                    "show_employee_profile to open the canvas, "
                    "or to expand_skill / run_task to operate "
                    "on the employee."
                ),
                mcp=Tool(),
            ),
            list_my_employees=Reader(
                request=None,
                response=ListEmployeesResponse,
                description=(
                    "List all employee IDs this user has hired."
                ),
                mcp=Tool(),
            ),
        ),
    ),
    Employee=Type(
        state=EmployeeState,
        methods=Methods(
            show_profile=UI(
                request=ShowProfileConfig,
                path="web/ui/profile",
                title="Employee Skill Tree",
                description=(
                    "Open the interactive skill-tree canvas for "
                    "an employee. Shows avatar, role, and an "
                    "expandable tree of skills and tasks. Use "
                    "`welcome_message` to greet the human."
                ),
            ),
            create=Writer(
                request=CreateEmployeeRequest,
                response=None,
                factory=True,
                mcp=None,
            ),
            get=Reader(
                request=None,
                response=GetEmployeeResponse,
                description=(
                    "Get the full profile of an employee: name, "
                    "role, avatar seed, and skill tree."
                ),
                mcp=Tool(),
            ),
            expand_skill=Writer(
                request=ExpandSkillRequest,
                response=None,
                description=(
                    "Decompose a skill into 2-4 concrete tasks "
                    "using Claude. Pass the skill_index "
                    "(0-based) of the skill to expand."
                ),
                mcp=Tool(),
            ),
            run_task=Writer(
                request=RunTaskRequest,
                response=RunTaskResponse,
                description=(
                    "Execute a task with a given scope of work. "
                    "Returns simulated agent output (a plan, "
                    "execution narration, and a deliverable). "
                    "Marks the task as complete."
                ),
                mcp=Tool(),
            ),
        ),
    ),
)
