"""Persona-generic sub-entry detection — synthetic resumes, no real files."""

from __future__ import annotations

import pytest

from validator.resume_understanding_validator import _detect_sub_entries

# Each experience line: Role | Company — Location | Mon YYYY – Mon YYYY
_ENGINEERING_EXPERIENCE = """
Senior Platform Engineer | Northwind Labs — Remote | Jan 2024 – Present
• Owned platform reliability for 3 regions

Staff Engineer | Contoso Systems — Remote | Jun 2021 – Dec 2023
• Led design reviews across 4 squads

Principal Engineer | Fabrikam Digital — Remote | Mar 2019 – May 2021
• Shipped core billing migration

Engineering Manager | Alpine Analytics — Remote | Aug 2016 – Feb 2019
• Managed 14-person delivery team

Tech Lead | Summit Software — Remote | Jan 2014 – Jul 2016
• Delivered API gateway rollout

Software Engineer | Harbor Tech — Remote | Sep 2011 – Dec 2013
• Built customer onboarding flows

Associate Engineer | Lakeside IT — Remote | Jul 2009 – Aug 2011
• Maintained integration test suite
"""

_ENGINEERING_CERTS = """
AWS Certified Solutions Architect | Mar 2022
PMP Certification | Jun 2021
Google Cloud Professional Certificate | Jan 2023
"""

_PRODUCT_EXPERIENCE = """
Director of Product | Orbit Commerce — Remote | Jan 2023 – Present
• Owned checkout roadmap end-to-end

Senior Product Manager | Nova Retail — Remote | Apr 2020 – Dec 2022
• Launched loyalty program for 2M users

Product Manager | Cedar Health — Remote | Jun 2017 – Mar 2020
• Drove patient portal adoption

Associate Product Manager | Pixel Media — Remote | Aug 2014 – May 2017
• Ran discovery for creator tools
"""

_PRODUCT_CERTS = """
PSPO I Certification | Sep 2021
HubSpot Inbound Certification | Apr 2020
"""

_MARKETING_EXPERIENCE = """
Head of Growth Marketing | Brightline Co — Remote | Feb 2022 – Present
• Scaled paid acquisition across 5 channels

Marketing Manager | Cedar Health — Remote | May 2018 – Jan 2022
• Owned lifecycle email program

Marketing Associate | Pixel Media — Remote | Jul 2015 – Apr 2018
• Ran social campaigns and reporting
"""

_MARKETING_CERTS = """
Meta Blueprint Certification | Nov 2021
HubSpot Content Marketing Certification | Mar 2020
Pursuing Google UX Design Certificate | Jan 2025
"""

_SALES_EXPERIENCE = """
Regional Sales Director | Vertex Solutions — Remote | Jan 2023 – Present
• Exceeded annual quota by 28%

Enterprise Account Executive | Orbit Commerce — Remote | Mar 2020 – Dec 2022
• Closed 9 seven-figure deals

Senior Sales Representative | Nova Retail — Remote | Jun 2017 – Feb 2020
• Expanded territory ARR 40%

Sales Development Representative | Cedar Health — Remote | Jan 2015 – May 2017
• Qualified 120+ enterprise opportunities monthly

Business Development Associate | Lakeside IT — Remote | Aug 2012 – Dec 2014
• Booked 35 discovery calls per week
"""

_SALES_CERTS = """
Salesforce Trailhead Ranger | Aug 2022
SPIN Selling Certified Practitioner | May 2021
"""


@pytest.mark.parametrize(
    "experience_text,expected_exp_count,cert_text,expected_cert_count",
    [
        (_ENGINEERING_EXPERIENCE, 7, _ENGINEERING_CERTS, 3),
        (_PRODUCT_EXPERIENCE, 4, _PRODUCT_CERTS, 2),
        (_MARKETING_EXPERIENCE, 3, _MARKETING_CERTS, 3),
        (_SALES_EXPERIENCE, 5, _SALES_CERTS, 2),
    ],
    ids=["engineering", "product", "marketing", "sales"],
)
def test_detect_sub_entries_persona_generic(
    experience_text: str,
    expected_exp_count: int,
    cert_text: str,
    expected_cert_count: int,
) -> None:
    blocks = _detect_sub_entries(experience_text, "experience")
    assert len(blocks) == expected_exp_count, (
        f"experience: expected {expected_exp_count}, got {len(blocks)}: "
        f"{[b['label'] for b in blocks]}"
    )

    cert_blocks = _detect_sub_entries(cert_text, "certifications")
    assert len(cert_blocks) == expected_cert_count, (
        f"certifications: expected {expected_cert_count}, got {len(cert_blocks)}: "
        f"{[b['label'] for b in cert_blocks]}"
    )
