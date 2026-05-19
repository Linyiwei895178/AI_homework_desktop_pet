"""
状态对应动作决策规则
"""

# TO_DO: 根据 pet_state 返回动作名称


def decide_action(pet_state) -> str:
    """
    根据桌宠状态决策应该执行的动作

    :param pet_state: PetState对象，包含 mood/energy/intimacy 属性
    :return: 动作名称字符串

    TO_DO:
    - 根据心情(mood)决定主动作
    - 根据能量(energy)决定是否需要补充
    - 根据亲密度(intimacy)决定互动程度
    - 返回动作名称如 "idle", "happy", "sad", "hungry", "angry"
    """

    # TO_DO: 根据 pet_state 返回动作名称

    # 能量低于30，优先执行 "hungry" 动作
    if pet_state.energy < 30:
        return "hungry"

    # 根据心情返回对应动作
    mood_action_map = {
        "happy": "happy",
        "sad": "sad",
        "angry": "angry",
        "hungry": "hungry",
        "neutral": "idle",
    }

    action = mood_action_map.get(pet_state.mood, "idle")

    # 高亲密度时增加互动积极性
    if pet_state.intimacy > 80 and action == "idle":
        action = "happy"

    return action
