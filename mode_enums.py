from enum import Enum, auto

class OperatingMode(Enum):
    """
    定义应用程序支持的各种工作模式。
    每个成员代表一种模式，其值是用于在配置文件和内部逻辑中引用的唯一键。
    """
    CLASSIC = "classic"
    CUSTOM = "custom"
    STUDENT = "student"
    PROFESSIONAL = "professional"
    FRAGMENTED_TIME = "fragmented_time"
    def display_name(self, config: dict) -> str:
        """
        返回该模式在UI中显示的名称。
        它会尝试从配置文件中动态加载名称，如果失败则返回一个硬编码的默认值。
        """
        # 为没有预设的模式提供默认名称
        if self in [OperatingMode.CLASSIC, OperatingMode.CUSTOM]:
            return {
                OperatingMode.CLASSIC: "经典模式 (手动调时)",
                OperatingMode.CUSTOM: "自定义模式",
            }.get(self)

        # 尝试从配置文件的 presets 中获取名称
        try:
            presets = config.get("presets", {})
            return presets.get(self.value, {}).get("name", f"{self.value.capitalize()} (名称未配置)")
        except Exception:
            return f"{self.value.capitalize()} (加载错误)"

    def description(self, config: dict) -> str:
        """
        返回该模式的详细说明。
        它会尝试从配置文件中动态加载说明，如果失败则返回一个提示信息。
        """
        if self == OperatingMode.CLASSIC:
            return "此模式下没有预设的循环，您可以手动设置专注和休息时间。"

        try:
            presets = config.get("presets", {})
            desc = presets.get(self.value, {}).get("description", "该模式的说明未在配置中找到。")
            # 使用 str.strip() 来移除由 YAML 多行字符串产生的任何前导/尾随空白
            return desc.strip()
        except Exception:
            return "加载模式说明时出错。"

    @classmethod
    def from_key(cls, key: str):
        """根据键字符串查找并返回对应的枚举成员。"""
        for member in cls:
            if member.value == key:
                return member
        # 如果找不到，默认返回经典模式，以确保程序健壮性
        return cls.CLASSIC

    @classmethod
    def get_advanced_modes(cls):
        """获取所有非经典的高级模式列表。"""
        return [
            cls.CUSTOM, 
            cls.STUDENT,
            cls.PROFESSIONAL,
            cls.FRAGMENTED_TIME
        ]