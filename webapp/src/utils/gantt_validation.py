# src/utils/gantt_validation.py

from dataclasses import dataclass, field


@dataclass
class ValidationContext:
    """Dados adicionais que as regras podem precisar."""
    category: dict | None = None
    existing_assignments: list = field(default_factory=list)
    exclude_assignment_id: str | None = None


class ValidationRule:
    name: str = ""

    def validate(self, data: dict, ctx: ValidationContext) -> list[str]:
        """Retorna lista de mensagens de erro. Lista vazia = passou."""
        raise NotImplementedError


class ValidationPipeline:
    def __init__(self, rules: list[ValidationRule]):
        self.rules = rules

    def run(self, data: dict, ctx: ValidationContext) -> list[str]:
        errors = []
        for rule in self.rules:
            errors.extend(rule.validate(data, ctx))
        return errors


# ---------------------------------------------------------------------------
# Regras concretas
# ---------------------------------------------------------------------------

class DateConsistencyRule(ValidationRule):
    name = "Datas consistentes"

    def validate(self, data, ctx):
        if data["data_hora_fim"] <= data["data_hora_inicio"]:
            return ["Data/hora de fim deve ser posterior à data/hora de início."]
        return []


class ActivityContainmentRule(ValidationRule):
    name = "Contenção na categoria"

    def validate(self, data, ctx):
        cat = ctx.category
        errors = []
        if data["data_hora_inicio"] < cat["data_hora_inicio"]:
            errors.append("Início da atividade anterior ao início da categoria pai.")
        if data["data_hora_fim"] > cat["data_hora_fim"]:
            errors.append("Fim da atividade posterior ao fim da categoria pai.")
        return errors


class AssignmentIntervalRule(ValidationRule):
    name = "Intervalo de atribuição"

    def validate(self, data, ctx):
        if data["data_hora_saida"] <= data["data_hora_entrada"]:
            return ["Data/hora de saída deve ser posterior à data/hora de entrada."]
        return []


class AssignmentConflictRule(ValidationRule):
    name = "Conflito de atribuição"

    def validate(self, data, ctx):
        inicio_novo = data["data_hora_entrada"]
        fim_novo    = data["data_hora_saida"]
        for a in (ctx.existing_assignments or []):
            if str(a["_id"]) == ctx.exclude_assignment_id:
                continue
            if inicio_novo < a["data_hora_saida"] and a["data_hora_entrada"] < fim_novo:
                return [
                    f"Conflito de atribuição: funcionário já alocado de "
                    f"{a['data_hora_entrada']:%d/%m %H:%M} a {a['data_hora_saida']:%d/%m %H:%M}."
                ]
        return []


# ---------------------------------------------------------------------------
# Pipelines por entidade
# ---------------------------------------------------------------------------

CATEGORY_PIPELINE   = ValidationPipeline([DateConsistencyRule()])
ACTIVITY_PIPELINE   = ValidationPipeline([DateConsistencyRule(), ActivityContainmentRule()])
ASSIGNMENT_PIPELINE = ValidationPipeline([AssignmentIntervalRule(), AssignmentConflictRule()])
