"""桌宠角色状态定义与切换逻辑。"""

from __future__ import annotations

import random
from enum import Enum


class PetState(str, Enum):
    """桌宠支持的三种显示状态。"""

    XIAOBAI = "xiaobai"
    XIAOJIMAO = "xiaojimao"
    TOGETHER = "together"

    @property
    def display_name(self) -> str:
        return {
            PetState.XIAOBAI: "小白",
            PetState.XIAOJIMAO: "小鸡毛",
            PetState.TOGETHER: "小白 + 小鸡毛",
        }[self]

    @property
    def reminder_subject(self) -> str:
        """返回当前场景用于提醒气泡的角色称呼。"""

        return {
            PetState.XIAOBAI: "小白",
            PetState.XIAOJIMAO: "小鸡毛",
            PetState.TOGETHER: "小白和小鸡毛一起",
        }[self]


def random_switch_state(
    current_state: PetState,
    rng: random.Random | None = None,
) -> PetState:
    """随机返回一个与当前状态不同的状态。"""

    random_source = rng or random
    choices = [state for state in PetState if state != current_state]
    return random_source.choice(choices)
