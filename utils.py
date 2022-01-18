from datetime import datetime
import json
import math


def apply_pagination(current_page, per_page, records: list):
    records_count = len(records)
    min_pages_count = 1
    pages_count = math.ceil(records_count / per_page) or min_pages_count
    if current_page > pages_count:
        init_page = 1
        current_page = init_page
    records_start_index = (current_page - 1) * per_page
    records_end_index = current_page * per_page
    records = records[records_start_index:records_end_index]
    return {'currentPage': current_page, 'pagesCount': pages_count, 'records': records}


def convert_mongo_data_to_json(data):
    return json.dumps(data, default=str)


def create_initial_status(companies: list):
    companies_map = {}
    for company in companies:
        company_name = company['name']
        companies_map[company_name] = {'lawyer': False, 'economist': False, 'director': False }
    return {'name': 'creating', 'companies': companies_map}


def define_action_on_status_and_acceptances(user_company_name, user_role, contact_status):
    status_name = contact_status['name']
    actions_map = {'creating': 'Harmonize', 'harmonization': 'Harmonize', 'harmonized': 'Sign', 'signing': 'Sign',
                   'signed': 'Archive'}
    action_on_status = actions_map.get(status_name, '')
    same_role_acceptance = contact_status['companies'][user_company_name][user_role]
    if same_role_acceptance or status_name in ['harmonized', 'signing'] and user_role != 'director':
        action_on_status = ''
    acceptance_names_map = {'harmonization': 'harmonized', 'signing': 'signed'}
    companies_acceptances = []
    if status_name in acceptance_names_map:
        accept_name = acceptance_names_map[status_name]
        companies = contact_status['companies']
        for company in companies:
            roles_acceptance = companies[company]
            acceptance = roles_acceptance['director'] if status_name == 'signing' else all(roles_acceptance.values())
            acceptance_name = accept_name if acceptance else 'pending'
            companies_acceptances.append([company, acceptance_name])
    return action_on_status, companies_acceptances


def key_func_for_sorting_comments(comment, contract_text):
    comment_number = comment['number']
    search_substring = f'<span style="background-color:hsl(40,{comment_number}%,80%);">'
    return contract_text.find(search_substring)


def remove_companies_from_invitation(invitation_variants, invitations):
    for invitation in invitations:
        invitation_type = invitation['type']
        companies_to_invite = invitation_variants[invitation_type]
        companies_id = [company['id'] for company in companies_to_invite]
        recipient_company_id = invitation['recipient']['company_id']
        if recipient_company_id in companies_id:
            company_to_remove_ind = companies_id.index(recipient_company_id)
            companies_to_invite.pop(company_to_remove_ind)
    for invitation_variant in list(invitation_variants):
        if not invitation_variants[invitation_variant]:
            del invitation_variants[invitation_variant]
    return invitation_variants


def transform_field(field_value, field_name):
    if field_name == 'creation_date':
        return datetime.strptime(field_value, '%d.%m.%y %H:%M:%S').strftime('%y.%m.%d %H:%M:%S')
    return field_value


def update_status(action_on_status, user_company_name, user_role, contact_status):
    current_status = contact_status['name']
    actions_map = {'Harmonize': ['creating', 'harmonization'], 'Sign': ['harmonized', 'signing'], 'Archive': ['signed']}
    if not current_status in actions_map[action_on_status]:
        return contact_status
    updated_status = contact_status.copy()
    updated_status['companies'][user_company_name][user_role] = True
    statuses = ['creating', 'harmonization', 'harmonized', 'signing', 'signed', 'archived']
    next_status = statuses[statuses.index(current_status) + 1] if current_status != 'archived' else ''
    if current_status in ['creating', 'harmonized', 'signed']:
        updated_status['name'] = next_status
        return updated_status
    companies = updated_status['companies']
    for company in companies:
        roles_acceptance = companies[company]
        acceptance = roles_acceptance['director'] if current_status == 'signing' else all(roles_acceptance.values())
        if not acceptance:
            return updated_status
    updated_status['name'] = next_status
    for company in companies:
        roles_acceptance = companies[company]
        companies[company] = {key: False for key in roles_acceptance}
    return updated_status
