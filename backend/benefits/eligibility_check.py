from typing import Dict, Optional, List
import ast
import inspect
import re

def eligibility_check(user_info: str) -> str:
    """
    Determines eligibility for various government benefits based on user information.
    Returns a formatted string with eligibility results and explanations.
    
    Parameters:
    user_info (dict): A dictionary containing user data (e.g., age, income, family status).

    Returns:
    str: Eligibility results with explanations for each benefit.
    """

    if "{" not in user_info:
        user_info = "{" + user_info 
    
    if "}" not in user_info:
        user_info += "}"

    match = re.search(r"{.*}", user_info, re.DOTALL) 
    if match: 
        cleaned_output = match.group(0).replace("{{","{").replace("}}","}")
    else:
        return ""
    
    all_user_info = ast.literal_eval(cleaned_output)

    if 'relevance' in all_user_info and all_user_info['relevance'] == False:
        return "Irrelevant"

    # Define benefit constraints with dynamic SSI conditions based on family and marital status
    benefit_constraints = {
        "SSI": {
            "single_adult": {
                "income": {"constraint": lambda income: income < 1971, "weight": 0.3, "description": "Income should be less than $1971 for single adults"},
                "non_work_income": {"constraint": lambda income: income < 963, "weight": 0.3, "description": "Non-work income should be less than $963 for single adults"},
                "resources": {"constraint": lambda resources: resources <= 2000, "weight": 0.2, "description": "Resources should be $2000 or less for individuals"}
            },
            "married_couple": {
                "income": {"constraint": lambda income: income < 2915, "weight": 0.3, "description": "Income should be less than $2915 for married couples"},
                "non_work_income": {"constraint": lambda income: income < 1435, "weight": 0.3, "description": "Non-work income should be less than $1435 for married couples"},
                "resources": {"constraint": lambda resources: resources <= 3000, "weight": 0.2, "description": "Resources should be $3000 or less for couples"}
            },
            "individual_parent_disabled_child": {
                "income": {"constraint": lambda income: income < 3897, "weight": 0.3, "description": "Income should be less than $3897 for an individual parent with a disabled child"},
                "non_work_income": {"constraint": lambda income: income < 1926, "weight": 0.3, "description": "Non-work income should be less than $1926 for an individual parent with a disabled child"},
                "resources": {"constraint": lambda resources: resources <= 2000, "weight": 0.2, "description": "Resources should be $2000 or less for individuals"}
            },
            "general": {
                "age_or_disability": {"constraint": lambda age, disability: age >= 65 or disability, "weight": 0.4, "description": "Age over 65 or has a disability"}
            }
        },
        "SSA": {
            "work_credits": {"constraint": lambda credits: credits >= 40, "weight": 0.5, "description": "Must have at least 40 work credits"},
            "age_for_retirement": {"constraint": lambda age: age >= 62, "weight": 0.3, "description": "Age 62 or older for early retirement benefits"}
        },
        "Medicare": {
            "eligibility_social_security": {"constraint": lambda eligible: eligible, "weight": 0.3, "description": "Eligible if they qualify for Social Security or Railroad Retirement benefits"},
            "age_or_work_history": {"constraint": lambda age, work_credits: age >= 65 or work_credits >= 40, "weight": 0.3, "description": "Age over 65 or eligible based on work history"},
            "disability_medical": {"constraint": lambda disability, condition: disability or condition in ['kidney_failure'], "weight": 0.3, "description": "Eligible based on disability or specific medical conditions like kidney failure"}
        },
        "SSDI": {
            "work_credits": {"constraint": lambda credits: credits >= 20, "weight": 0.4, "description": "At least 20 recent work credits"},
            "disability_prevents_sga": {"constraint": lambda disability, sga: disability and not sga, "weight": 0.3, "description": "Medical condition prevents substantial gainful activity"},
            "specific_condition": {"constraint": lambda condition: condition in ['terminal_illness', 'serious_condition'], "weight": 0.3, "description": "Eligible if diagnosed with a terminal or serious condition"}
        }
    }

    def categorize_eligibility(score: float) -> str:
        if score >= 90:
            return "Highly likely eligible"
        elif score >= 70:
            return "Likely eligible"
        elif score >= 40:
            return "Maybe eligible"
        else:
            return "Not eligible"

    def calculate_eligibility_score(user_info,benefit: str) -> Dict[str, any]:
        score = 0.0
        met_constraints: List[str] = []
        unmet_constraints: List[str] = []
        missing_constraints: List[str] = []

        # Select constraints based on family and marital status for SSI
        if benefit == "SSI":
            family_status = user_info.get("family_status", "single_adult")
            if family_status == None:
                family_status = "single_adult"
                missing_constraints.append("Marital status unknown; we need further information on marital status for SSI. Assuming Single Adult for now.")
            constraints = benefit_constraints[benefit].get(family_status, benefit_constraints[benefit]["single_adult"])
            general_constraints = benefit_constraints[benefit]["general"]
        else:
            constraints = benefit_constraints.get(benefit, {})
            general_constraints = {}

        total_weight = sum(c["weight"] for c in constraints.values()) + sum(general_constraints[c]["weight"] for c in general_constraints)

        for _, data in {**constraints, **general_constraints}.items():
            constraint_func = data["constraint"]
            weight = data["weight"]
            description = data["description"]

            # Get the expected argument names for the constraint function
            expected_args = inspect.signature(constraint_func).parameters.keys()
            # Filter user_info to match the expected arguments for this constraint
            filtered_user_info = {arg: user_info.get(arg) for arg in expected_args}

            if any(value is None for value in filtered_user_info.values()):
                score += weight * 0.5
                missing_constraints.append(description)
            elif constraint_func(**filtered_user_info):
                score += weight
                met_constraints.append(description)
            else:
                unmet_constraints.append(description)

        normalized_score = score / total_weight * 100
        category = categorize_eligibility(normalized_score)

        return {
            "score": normalized_score,
            "category": category,
            "met_constraints": met_constraints,
            "unmet_constraints": unmet_constraints,
            "missing_constraints": missing_constraints
        }

    def generate_output(results: Dict[str, Dict[str, any]]) -> str:
        output = ""

        sorted_results = sorted(results.items(),key=lambda k: k[1]['score'],reverse=True)
        for benefit, result in sorted_results:
            output += f"Benefit: {benefit}\n"
            output += f"  Category: {result['category']}\n"
            output += f"  Met Constraints: {', '.join(result['met_constraints'])}\n"
            output += f"  Unmet Constraints: {', '.join(result['unmet_constraints'])}\n"
            output += f"  Missing Constraints: {', '.join(result['missing_constraints'])}\n\n"
        return output

    results = {}
    for benefit in benefit_constraints.keys():
        results[benefit] = calculate_eligibility_score(all_user_info,benefit)
    output = generate_output(results)
    print("Output {}".format(output))
    return str(user_info) + "\n" + output
