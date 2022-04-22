import logging
from openfisca_tools.data import PublicDataset
import h5py
from openfisca_us.data.datasets.cps.raw_cps import RawCPS
from openfisca_us.data.storage import OPENFISCA_US_MICRODATA_FOLDER
from pandas import DataFrame, Series
import numpy as np


class CPS(PublicDataset):
    name = "cps"
    label = "CPS"
    model = "openfisca_us"
    folder_path = OPENFISCA_US_MICRODATA_FOLDER

    url_by_year = {
        2020: "https://github.com/PolicyEngine/openfisca-us/releases/download/cps-v0/cps_2020.h5"
    }

    def generate(self, year: int):
        """Generates the Current Population Survey dataset for OpenFisca-US microsimulations.

        Args:
            year (int): The year of the Raw CPS to use.
        """

        # Prepare raw CPS tables
        year = int(year)
        if year not in RawCPS.years:
            logging.info(f"Generating raw CPS for year {year}.")
            RawCPS.generate(year)

        raw_data = RawCPS.load(year)
        cps = h5py.File(self.file(year), mode="w")

        person, tax_unit, family, spm_unit, household = [
            raw_data[entity]
            for entity in (
                "person",
                "tax_unit",
                "family",
                "spm_unit",
                "household",
            )
        ]

        add_id_variables(cps, person, tax_unit, family, spm_unit, household)
        add_personal_variables(cps, person)
        add_personal_income_variables(cps, person)
        add_spm_variables(cps, spm_unit)
        add_household_variables(cps, household)

        raw_data.close()
        cps.close()


def add_id_variables(
    cps: h5py.File,
    person: DataFrame,
    tax_unit: DataFrame,
    family: DataFrame,
    spm_unit: DataFrame,
    household: DataFrame,
):
    """Add basic ID and weight variables.

    Args:
        cps (h5py.File): The CPS dataset file.
        person (DataFrame): The person table of the ASEC.
        tax_unit (DataFrame): The tax unit table created from the person table
            of the ASEC.
        family (DataFrame): The family table of the ASEC.
        spm_unit (DataFrame): The SPM unit table created from the person table
            of the ASEC.
        household (DataFrame): The household table of the ASEC.
    """
    # Add primary and foreign keys
    cps["person_id"] = person.PH_SEQ * 100 + person.P_SEQ
    cps["family_id"] = family.FH_SEQ * 10 + family.FFPOS
    cps["household_id"] = household.H_SEQ
    cps["person_tax_unit_id"] = person.TAX_ID
    cps["person_spm_unit_id"] = person.SPM_ID
    cps["tax_unit_id"] = tax_unit.TAX_ID
    cps["spm_unit_id"] = spm_unit.SPM_ID
    cps["person_household_id"] = person.PH_SEQ
    cps["person_family_id"] = person.PH_SEQ * 10 + person.PF_SEQ

    # Add weights
    # Weights are multiplied by 100 to avoid decimals
    cps["person_weight"] = person.A_FNLWGT / 1e2
    cps["family_weight"] = family.FSUP_WGT / 1e2

    # Tax unit weight is the weight of the containing family.
    family_weight = Series(
        cps["family_weight"][...], index=cps["family_id"][...]
    )
    person_family_id = cps["person_family_id"][...]
    persons_family_weight = Series(family_weight[person_family_id])
    cps["tax_unit_weight"] = persons_family_weight.groupby(
        cps["person_tax_unit_id"][...]
    ).first()

    cps["spm_unit_weight"] = spm_unit.SPM_WEIGHT / 1e2

    cps["household_weight"] = household.HSUP_WGT / 1e2


def add_personal_variables(cps: h5py.File, person: DataFrame):
    """Add personal demographic variables.

    Args:
        cps (h5py.File): The CPS dataset file.
        person (DataFrame): The CPS person table.
    """

    # The CPS edits age as follows:
    # 0-79 => 0-79
    # 80-84  => 80
    # 85+ => 85
    # We assign the 80 ages randomly between 80 and 85
    # to avoid unrealistically bunching at 80
    cps["age"] = np.where(
        person.A_AGE.between(80, 85),
        80 + 5 * np.random.rand(len(person)),
        person.A_AGE,
    )


def add_personal_income_variables(cps: h5py.File, person: DataFrame):
    """Add income variables.

    Args:
        cps (h5py.File): The CPS dataset file.
        person (DataFrame): The CPS person table.
    """
    cps["employment_income"] = person.WSAL_VAL
    cps["self_employment_income"] = person.SEMP_VAL
    cps["e02100"] = person.FRSE_VAL
    cps["social_security"] = person.SS_VAL
    cps["e02300"] = person.UC_VAL

    # Pensions/annuities
    other_inc_type = person.OI_OFF
    cps["e01500"] = other_inc_type.isin((2, 13)) * person.OI_VAL

    # Alimony
    cps["e00800"] = (person.OI_OFF == 20) * person.OI_VAL


def add_spm_variables(cps: h5py.File, spm_unit: DataFrame):
    SPM_RENAMES = dict(
        spm_unit_total_income="SPM_TOTVAL",
        snap="SPM_SNAPSUB",
        spm_unit_capped_housing_subsidy="SPM_CAPHOUSESUB",
        free_school_meals="SPM_SCHLUNCH",
        spm_unit_energy_subsidy="SPM_ENGVAL",
        spm_unit_wic="SPM_WICVAL",
        spm_unit_fica="SPM_FICA",
        spm_unit_federal_tax="SPM_FEDTAX",
        spm_unit_state_tax="SPM_STTAX",
        spm_unit_work_childcare_expenses="SPM_CAPWKCCXPNS",
        spm_unit_medical_expenses="SPM_MEDXPNS",
        spm_unit_spm_threshold="SPM_POVTHRESHOLD",
        spm_unit_net_income_reported="SPM_RESOURCES",
    )

    for openfisca_variable, asec_variable in SPM_RENAMES.items():
        cps[openfisca_variable] = spm_unit[asec_variable]

    cps["reduced_price_school_meals"] = cps["free_school_meals"][...] * 0


def add_household_variables(cps: h5py.File, household: DataFrame):
    cps["fips"] = household.GESTFIPS


CPS = CPS()
