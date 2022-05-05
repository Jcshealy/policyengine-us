from openfisca_us.model_api import *


class MedicaidPersonType(Enum):
    ADULT_WITHOUT_DEPENDENT = "Adult without dependent"
    ADULT_WITH_DEPENDENT = "Adult with dependent"
    PREGNANT = "Pregnant adult"
    CHILD_AGE_0 = "Child age 0"
    CHILD_AGE_1_5 = "Child age 1 to 5"
    CHILD_AGE_6_18 = "Child age 6 to 18"
    CHILD_AGE_19_20 = "Adult under 21 (covered as child)"


class medicaid_person_type(Variable):
    value_type = Enum
    possible_values = MedicaidPersonType
    default_value = MedicaidPersonType.ADULT_WITHOUT_DEPENDENT
    entity = Person
    definition_period = YEAR
    label = "Medicaid person type"
    documentation = "Person type for Medicaid"

    def formula(person, period, parameters):
        # Get the person's age.
        age = person("age", period)
        # Get the existence of dependents, as defined by people 18 or younger.
        has_dependents = person.spm_unit.any(
            person.spm_unit.members("age", period) < 19
        )
        under_21_qualifies = parameters(period).hhs.medicaid.under_21_qualifies_as_child
        state = person.household("state_code_str", period)
        state_has_under_21_child_category = under_21_qualifies[state]
        return select(
            [age == 0, age < 6, age < 19, (age < 21) & state_has_under_21_child_category, has_dependents, True],
            [
                MedicaidPersonType.CHILD_AGE_0,
                MedicaidPersonType.CHILD_AGE_1_5,
                MedicaidPersonType.CHILD_AGE_6_18,
                MedicaidPersonType.CHILD_AGE_19_20,
                MedicaidPersonType.ADULT_WITH_DEPENDENT,
                MedicaidPersonType.ADULT_WITHOUT_DEPENDENT,
            ],
        )
