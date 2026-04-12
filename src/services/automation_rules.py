from typing import List, Dict, Any


class AutomationRules:
    """预设自动化规则"""

    RULES: Dict[str, Any] = {
        "new_customer_welcome": {
            "name": "新客户欢迎",
            "trigger": "event.customer.created",
            "actions": [
                {"type": "email.send", "template": "welcome"},
                {"type": "tag.add", "tag": "new_customer"},
                {"type": "task.create", "title": "新客户跟进"}
            ]
        },
        "opportunity_stage_changed": {
            "name": "商机阶段变更通知",
            "trigger": "event.opportunity.stage_changed",
            "actions": [
                {"type": "notification.send", "to": "owner"},
                {"type": "activity.log", "content": "商机阶段变更"}
            ]
        },
        "inactive_customer_alert": {
            "name": "沉睡客户预警",
            "trigger": "scheduled.daily",
            "conditions": [
                {"field": "last_activity_at", "operator": "<", "value": "30d"}
            ],
            "actions": [
                {"type": "notification.send", "to": "owner"},
                {"type": "task.create", "title": "跟进沉睡客户"}
            ]
        },
        "deal_won_celebration": {
            "name": "成交庆祝",
            "trigger": "event.opportunity.stage_changed",
            "conditions": [
                {"field": "stage", "operator": "==", "value": "won"}
            ],
            "actions": [
                {"type": "email.send", "template": "congratulations"},
                {"type": "activity.log", "content": "成交记录"}
            ]
        }
    }

    def get_available_rules(self) -> List[Dict]:
        """获取所有可用规则"""
        return [
            {"key": key, **value}
            for key, value in self.RULES.items()
        ]

    def apply_rule(self, rule_name: str, context: Dict) -> Dict:
        """应用指定规则"""
        rule = self.RULES.get(rule_name)
        if not rule:
            raise ValueError(f"Rule '{rule_name}' not found")

        results = []
        for action in rule.get("actions", []):
            action_type = action.get("type")
            if action_type == "email.send":
                results.append({
                    "type": "email.send",
                    "status": "sent",
                    "template": action.get("template"),
                })
            elif action_type == "notification.send":
                results.append({
                    "type": "notification.send",
                    "status": "sent",
                    "to": action.get("to"),
                })
            elif action_type == "tag.add":
                results.append({
                    "type": "tag.add",
                    "status": "added",
                    "tag": action.get("tag"),
                })
            elif action_type == "task.create":
                results.append({
                    "type": "task.create",
                    "status": "created",
                    "title": action.get("title"),
                })
            elif action_type == "activity.log":
                results.append({
                    "type": "activity.log",
                    "status": "logged",
                    "content": action.get("content"),
                })

        return {
            "rule": rule_name,
            "rule_name_display": rule.get("name"),
            "trigger": rule.get("trigger"),
            "actions_executed": results,
        }
