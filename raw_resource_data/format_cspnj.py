from copy import deepcopy 
import re
from utils import BASE_DIR

def is_date(line):
    """Determine if a line is in the date format MM/DD/YYYY
    Arguments:
        line: String
    
    Returns: Boolean, whether the line is a date"""

    return re.match(r"\d{2}/\d{2}/\d{4}", line)

def raw_cspnj_to_list(file_loc):
    data = open(file_loc).read().strip().split("\n")
    all_fields = ['name','county','city','last updated','wellness dimension']

    all_counties = {"atlantic","bergen","burlington","camden",
                "cape may","cumberland","essex","gloucester","hudson","hunterdon",
                "mercer","middlesex","monmouth","morris","ocean","passaic",
                "salem","somerset","sussex","union","warren"}
    wellness_dimensions = {'emotional', 'financial', 'intellectual', 'occupational', 
                        'physical', 'social', 'spiritual', 'environmental'}
    default_curr_entry = {'name': '','county': '', 'city': '','last updated': '', 'wellness dimension': ''}

    all_entries = []
    curr_entry = {}
    curr_field_idx = 0

    for line in data:
        line = line.strip()

        if is_date(line):
            curr_field_idx = 3
        elif line.lower() in wellness_dimensions:
            curr_field_idx = 4
        elif line.lower() in all_counties:
            curr_field_idx = 1
        else:
            if curr_field_idx == 1:
                curr_field_idx = 2
            elif curr_field_idx == 4:
                all_entries.append(curr_entry)
                curr_entry = deepcopy(default_curr_entry)
                curr_field_idx = 0

        curr_entry[all_fields[curr_field_idx]] = line
        curr_field_idx += 1
        if curr_field_idx == len(all_fields):
            all_entries.append(curr_entry)
            curr_entry = deepcopy(default_curr_entry)
            curr_field_idx = 0
    return [i['name'] for i in all_entries]

all_entries = raw_cspnj_to_list(f"{BASE_DIR}/data/raw_cspnj.txt")
w = open(BASE_DIR / "data/cspnj_resources.txt","w")
w.write("\n".join(all_entries))
w.close()