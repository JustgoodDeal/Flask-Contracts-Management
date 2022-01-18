import copy
import json
import mongo
import os
import settings
import utils
from bson import ObjectId
from celery import Celery
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, jsonify, request, Response
from flask_mail import Mail, Message


load_dotenv()


def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=app.config['result_backend'],
        broker=app.config['broker_url']
    )
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery


app = Flask(__name__)
app.config.from_object(settings)
app.config.update(
    broker_url=os.environ.get("broker_url"),
    result_backend=os.environ.get("result_backend"),
    MAIL_USERNAME=os.environ.get("MAIL_USERNAME"),
    MAIL_PASSWORD=os.environ.get("MAIL_PASSWORD"),
    MAIL_DEFAULT_SENDER=os.environ.get("MAIL_USERNAME"),
)

mail = Mail(app)

celery = make_celery(app)
# celery -A app.celery worker --loglevel=info --pool=solo


@celery.task
def send_email_notification(contract_id, message_text, receivers_emails):
    html_content = f'<p>New notification under contract № {contract_id}:</p> ' \
                   f'<p>"{message_text} "</p>'
    subject = f'Contracts management notification'
    msg = Message(subject, html=html_content, sender=app.config['MAIL_DEFAULT_SENDER'], recipients=receivers_emails)
    with app.app_context():
        mail.send(msg)


@app.route('/invitation/change/<invitation_id>/<new_status>', methods=['GET'])
def change_invitation_status(invitation_id, new_status):
    invitation = mongo.find_one_document('invitation', {'_id': ObjectId(invitation_id)})
    invitation['status'] = new_status
    mongo.update_one_document('invitation', invitation_id, invitation)
    return jsonify('Changed')


@app.route('/items/check/<employee_id>', methods=['GET'])
def check_new_items(employee_id):
    new_notification = bool(list(mongo.find_documents('notification', {'recipient_id': employee_id, 'is_read': False})))
    new_invitation = bool(list(mongo.find_documents('invitation', {'recipient.id': employee_id, 'status': 'pending'})))
    new_dialog = bool(list(mongo.find_documents('message', {f'is_read.{employee_id}': False})))
    return jsonify({'Dialogs': new_dialog, 'Invitations': new_invitation, 'Notifications': new_notification})


@app.route('/comments', methods=['GET'])
def get_comments():
    contract_id = request.args.get('contract_id')
    comments = list(mongo.find_documents('comment', {'contract_id': contract_id}))
    comments = json.loads(utils.convert_mongo_data_to_json(comments))
    for comment in comments:
        comment['related_comments'] = sorted(comment['related_comments'], key=lambda comment: utils.transform_field(
            comment['creation_date'], 'creation_date'))
        for related_comment in comment['related_comments']:
            related_comment['creation_date'] = datetime.strptime(related_comment['creation_date'], '%d.%m.%y %H:%M:%S')\
                .strftime('%d.%m.%y %H:%M')
    contract = mongo.find_one_document('contract', {'_id': ObjectId(contract_id)})
    comments = sorted(comments, key=lambda comment: utils.key_func_for_sorting_comments(comment, contract['text']))
    return jsonify(comments)


@app.route('/companies', methods=['GET'])
def get_companies():
    companies = list(mongo.find_documents('company', {}))
    companies = json.loads(utils.convert_mongo_data_to_json(companies))
    employee_id = request.args.get('user_id')
    employee_company_id = mongo.find_one_document('employee', {'_id': ObjectId(employee_id)})['company_id']
    zesla_group_id = '60338c13136d90fcdc76de24'
    default_companies = []
    companies_to_choose = []
    for company in companies:
        if company['_id'] in [employee_company_id, zesla_group_id]:
            if default_companies and default_companies[0] == company:
                continue
            default_companies.append(company)
        else:
            companies_to_choose.append(company)
    return jsonify({'defaultCompanies': default_companies, 'companiesToChoose': companies_to_choose})


@app.route('/contract/<contract_id>/<employee_id>', methods=['GET'])
def get_contract(contract_id, employee_id):
    contract = mongo.find_one_document('contract', {'_id': ObjectId(contract_id)})
    contract = json.loads(utils.convert_mongo_data_to_json(contract))
    creation_date = datetime.strptime(contract['creation_date'], '%d.%m.%y %H:%M:%S').strftime('%d.%m.%y %H:%M')
    contract['creation_date'] = creation_date
    employee = mongo.find_one_document('employee', {'_id': ObjectId(employee_id)})
    user_company = mongo.find_one_document('company', {'_id': ObjectId(employee['company_id'])})['name']
    user_role = mongo.find_one_document('role', {'_id': ObjectId(employee['role_id'])})['name']
    action, acceptances = utils.define_action_on_status_and_acceptances(user_company, user_role, contract['status'])
    contract.update({'actionOnStatus': action, 'companiesAcceptances': acceptances})
    return jsonify(contract)


@app.route('/contracts/<employee_id>', methods=['GET'])
def get_contracts(employee_id):
    employee = mongo.find_one_document('employee', {'_id': ObjectId(employee_id)})
    employee_company_id = employee['company_id']
    contracts = list(mongo.find_documents('contract', {'companies': {'$elemMatch': {'id': employee_company_id}}}))
    contracts = json.loads(utils.convert_mongo_data_to_json(contracts))
    sorting_field = request.args.get('field')
    if sorting_field == 'undefined':
        contracts = sorted(contracts, key=lambda contract: utils.transform_field(
        contract['creation_date'], 'creation_date'), reverse=True)
    else:
        reverse = True if request.args.get('reverse') == 'true' else False
        if sorting_field == 'status':
            contracts = sorted(contracts, key=lambda contract: contract['status']['name'], reverse=reverse)
        else:
            contracts = sorted(contracts, key=lambda contract: utils.transform_field(
                contract[sorting_field], sorting_field), reverse=reverse)
    current_page, per_page = int(request.args.get('page')), int(request.args.get('per_page'))
    pagination_entities = utils.apply_pagination(current_page, per_page, contracts)
    for contract in pagination_entities['records']:
        creation_date = datetime.strptime(contract['creation_date'], '%d.%m.%y %H:%M:%S').strftime('%d.%m.%y %H:%M')
        contract['creation_date'] = creation_date
    return jsonify(pagination_entities)


@app.route('/contract/versions/<contract_id>/<employee_id>', methods=['GET'])
def get_contract_versions(contract_id, employee_id):
    versions = list(mongo.find_documents('version', {'contract_id': contract_id, 'creator_id': employee_id}))
    versions = json.loads(utils.convert_mongo_data_to_json(versions))
    versions = sorted(versions, key=lambda version: utils.transform_field(version['creation_date'], 'creation_date'))
    for version in versions:
        creation_date = datetime.strptime(version['creation_date'], '%d.%m.%y %H:%M:%S').strftime('%d.%m.%y %H:%M')
        version['creation_date'] = creation_date
    return jsonify(versions)


@app.route('/dialog/variants/<contract_id>/<employee_id>', methods=['GET'])
def get_dialog_variants(contract_id, employee_id):
    contract = mongo.find_one_document('contract', {'_id': ObjectId(contract_id)})
    employees_for_dialog = []
    for company in contract['companies']:
        company_employees = mongo.find_documents('employee', {'company_id': company['id']})
        for employee in company_employees:
            if employee_id != str(employee['_id']):
                employees_for_dialog.append(
                    {'id': str(employee['_id']), 'name': employee['name'], 'companyName': company['name']}
                )
    query = {'contract_id': contract_id, 'participants': {'$elemMatch': {'id': employee_id}}}
    existing_dialogs = mongo.find_documents('dialog', query)
    everybody = {'id': 'everybody', 'name': 'Everybody', 'companyName': ''}
    employees_to_exclude = []
    for dialog in existing_dialogs:
        min_participants_count = 2
        if len(dialog['participants']) == min_participants_count:
            interlocutor_id = [user['id'] for user in dialog['participants'] if user['id'] != employee_id][0]
            employees_to_exclude.append(interlocutor_id)
        else:
            everybody = False
    employees_for_dialog = [employee for employee in employees_for_dialog if employee['id'] not in employees_to_exclude]
    employees_for_dialog = sorted(employees_for_dialog, key=lambda user: (user['companyName'], user['name']))
    if everybody:
        employees_for_dialog = [everybody] + employees_for_dialog
    return jsonify(employees_for_dialog)


@app.route('/dialog/<dialog_id>/<employee_id>', methods=['GET'])
def get_dialog(dialog_id, employee_id):
    dialog = mongo.find_one_document('dialog', {'_id': ObjectId(dialog_id)})
    contract_id, participants = dialog['contract_id'], dialog['participants']
    messages = list(mongo.find_documents('message', {'dialog_id': dialog_id}))
    for message in messages:
        if message['sender']['id'] == employee_id:
            message['is_read'] = any(message['is_read'].values())
        else:
            message['is_read'][employee_id] = True
            mongo.update_one_document('message', str(message['_id']), message)
            message['is_read'] = True
        message['_id'] = str(message['_id'])
    messages = sorted(messages, key=lambda message: utils.transform_field(message['creation_date'], 'creation_date'))
    return jsonify({'messages': messages, 'contractId': contract_id, 'participants': participants})


@app.route('/dialogs/<employee_id>', methods=['GET'])
def get_dialogs(employee_id):
    contract_id = request.args.get('contract_id')
    query = {'participants': {'$elemMatch': {'id': employee_id}}}
    if contract_id != 'undefined':
        query['contract_id'] = contract_id
    dialogs = mongo.find_documents('dialog', query)
    dialogs_entities = []
    for dialog in dialogs:
        dialog_id, dialog_contract_id, participants = str(dialog['_id']), dialog['contract_id'], dialog['participants']
        dialog_messages = list(mongo.find_documents('message', {'dialog_id': dialog_id}))
        latest_message = sorted(dialog_messages, key=lambda message: utils.transform_field(
            message['creation_date'], 'creation_date'), reverse=True)[0]
        latest_message = json.loads(utils.convert_mongo_data_to_json(latest_message))
        if latest_message['sender']['id'] == employee_id:
            latest_message['is_read'] = any(latest_message['is_read'].values())
        else:
            latest_message['is_read'] = latest_message['is_read'][employee_id]
        latest_message.update({'contract_id': dialog_contract_id, 'participants': participants})
        dialogs_entities.append(latest_message)
    if request.args.get('page') == 'undefined':
        dialogs_entities = sorted(dialogs_entities, key=lambda message: utils.transform_field(
            message['creation_date'], 'creation_date'), reverse=True)
        return jsonify({'currentPage': 1, 'pagesCount': 1, 'records': dialogs_entities})
    sorting_field = request.args.get('field')
    reverse = True
    if sorting_field == 'undefined':
        sorting_field = 'creation_date'
    else:
        reverse = True if request.args.get('reverse') == 'true' else False
    dialogs_entities = sorted(dialogs_entities, key=lambda message: utils.transform_field(
        message[sorting_field], sorting_field), reverse=reverse)
    current_page, per_page = int(request.args.get('page')), int(request.args.get('per_page'))
    pagination_entities = utils.apply_pagination(current_page, per_page, dialogs_entities)
    return jsonify(pagination_entities)


@app.route('/employees/roles/<employee_id>', methods=['GET'])
def get_employees_roles(employee_id):
    employee = mongo.find_one_document('employee', {'_id': ObjectId(employee_id)})
    employee_company_id = employee['company_id']
    company_employees = mongo.find_documents('employee', {'company_id': employee_company_id})
    employees_info = []
    for employee in company_employees:
        role_name = mongo.find_one_document('role', {'_id': ObjectId(employee['role_id'])})['name']
        employee_info = {'employeeId': str(employee['_id']), 'employeeName': employee['name'], 'savedRole': role_name}
        employees_info.append(employee_info)
    employees_info = sorted(employees_info, key=lambda employee_info: employee_info['employeeName'])
    return jsonify(employees_info)


@app.route('/invitation/variants/<contract_id>/<employee_id>', methods=['GET'])
def get_invitation_variants(contract_id, employee_id):
    contract = mongo.find_one_document('contract', {'_id': ObjectId(contract_id)})
    employee = mongo.find_one_document('employee', {'_id': ObjectId(employee_id)})
    companies_to_invite = [company for company in contract['companies'] if company['id'] != employee['company_id']]
    types_map = {
        'creating': {'editing': copy.deepcopy(companies_to_invite),
                     'harmonization': copy.deepcopy(companies_to_invite)},
        'harmonization': {'harmonization': copy.deepcopy(companies_to_invite)},
        'harmonized': {'signing': copy.deepcopy(companies_to_invite)},
        'signing': {'signing': copy.deepcopy(companies_to_invite)}
    }
    invitation_variants = types_map.get(contract['status']['name'], {})
    if invitation_variants:
        invitation_types = list(invitation_variants.keys())
        queries = []
        for invitation_type in invitation_types:
            queries.append({'contract_id': contract_id, 'type': invitation_type})
        invitations = mongo.find_documents_under_operator('invitation', 'or', queries)
        invitation_variants = utils.remove_companies_from_invitation(invitation_variants, invitations)
    return jsonify(invitation_variants)


@app.route('/invitations/<employee_id>', methods=['GET'])
def get_invitations(employee_id):
    contract_id = request.args.get('contract_id')
    queries = [{'creator.id': employee_id}, {'recipient.id': employee_id}]
    if contract_id != 'undefined':
        for query in queries:
            query['contract_id'] = contract_id
    invitations = list(mongo.find_documents_under_operator('invitation', 'or', queries))
    invitations = json.loads(utils.convert_mongo_data_to_json(invitations))
    sorting_field = request.args.get('field')
    if sorting_field == 'undefined':
        invitations = sorted(invitations, key=lambda invitation: utils.transform_field(
        invitation['creation_date'], 'creation_date'), reverse=True)
    else:
        reverse = True if request.args.get('reverse') == 'true' else False
        if sorting_field in ['creator', 'recipient']:
            invitations = sorted(invitations, key=lambda invitation: invitation[sorting_field]['name'], reverse=reverse)
        else:
            invitations = sorted(invitations, key=lambda invitation: utils.transform_field(
                invitation[sorting_field], sorting_field), reverse=reverse)
    current_page, per_page = int(request.args.get('page')), int(request.args.get('per_page'))
    pagination_entities = utils.apply_pagination(current_page, per_page, invitations)
    for invitation in pagination_entities['records']:
        creation_date = datetime.strptime(invitation['creation_date'], '%d.%m.%y %H:%M:%S').strftime('%d.%m.%y %H:%M')
        invitation['creation_date'] = creation_date
        user_is_creator = invitation['creator']['id'] == employee_id
        actions = not user_is_creator and invitation['status'] == 'pending'
        invitation.update({'actions': actions, 'userIsCreator': user_is_creator})
    return jsonify(pagination_entities)


@app.route('/notifications/<employee_id>', methods=['GET'])
def get_notifications(employee_id):
    contract_id = request.args.get('contract_id')
    query = {'recipient_id': employee_id}
    if contract_id != 'undefined':
        query['contract_id'] = contract_id
    notifications = list(mongo.find_documents('notification', query))
    notifications = json.loads(utils.convert_mongo_data_to_json(notifications))
    sorting_field = request.args.get('field')
    reverse = True
    if sorting_field == 'undefined':
        sorting_field = 'creation_date'
    else:
        reverse = True if request.args.get('reverse') == 'true' else False
    notifications = sorted(notifications, key=lambda notification: utils.transform_field(
        notification[sorting_field], sorting_field), reverse=reverse)
    current_page, per_page = int(request.args.get('page')), int(request.args.get('per_page'))
    pagination_entities = utils.apply_pagination(current_page, per_page, notifications)
    for notification in pagination_entities['records']:
        creation_date = datetime.strptime(notification['creation_date'], '%d.%m.%y %H:%M:%S').strftime('%d.%m.%y %H:%M')
        notification['creation_date'] = creation_date
    return jsonify(pagination_entities)


@app.route('/user', methods=['GET'])
def get_user():
    username = request.args.get('name')
    user = mongo.find_one_document('employee', {'name': username})
    if user:
        user_role = mongo.find_one_document('role', {'_id': ObjectId(user['role_id'])})['name']
        user = {'userId': user['_id'], 'userRole': user_role}
    else:
        user = ''
    return Response(utils.convert_mongo_data_to_json(user), mimetype='application/json')


@app.route('/notification/read/<notification_id>', methods=['GET'])
def make_notification_read(notification_id):
    notification = mongo.find_one_document('notification', {'_id': ObjectId(notification_id)})
    notification['is_read'] = True
    mongo.update_one_document('notification', notification_id, notification)
    return jsonify('Changed')


@app.route('/contract/version/save/<contract_id>/<employee_id>', methods=['GET'])
def save_contract_version(contract_id, employee_id):
    contract = mongo.find_one_document('contract', {'_id': ObjectId(contract_id)})
    version = {
        'contract_id': contract_id, 'creator_id': employee_id, 'text': contract['text'],
        'creation_date': datetime.now().strftime('%d.%m.%y %H:%M:%S'), 'contract_status': contract['status']['name']
    }
    mongo.insert_one_document('version', version)
    return jsonify('Saved')


@app.route('/contract/status/update/<contract_id>/<employee_id>', methods=['GET'])
def update_contract_status(contract_id, employee_id):
    action_on_status = request.args.get('action')
    contract = mongo.find_one_document('contract', {'_id': ObjectId(contract_id)})
    contract = json.loads(utils.convert_mongo_data_to_json(contract))
    employee = mongo.find_one_document('employee', {'_id': ObjectId(employee_id)})
    user_company = mongo.find_one_document('company', {'_id': ObjectId(employee['company_id'])})['name']
    user_role = mongo.find_one_document('role', {'_id': ObjectId(employee['role_id'])})['name']
    initial_status_name = contract['status']['name']
    updated_status = utils.update_status(action_on_status, user_company, user_role, contract['status'])
    final_status_name = updated_status['name']
    contract['status'] = updated_status
    del contract['_id']
    mongo.update_one_document('contract', contract_id, contract)
    invitations_types_map = {'harmonization': 'editing', 'harmonized': 'harmonization', 'signed': 'signing'}
    invitation_type_to_delete = invitations_types_map.get(final_status_name)
    if invitation_type_to_delete:
        mongo.delete_many_documents('invitation', {'contract_id': contract_id, 'type': invitation_type_to_delete})
    notifications_types_map = {
        ('creating', 'harmonization'): 'harmonization',
        ('harmonization', 'harmonized'): 'signing',
        ('signed', 'archived'): 'archived',
    }
    notification_type = notifications_types_map.get((initial_status_name, final_status_name))
    if notification_type:
        contract_companies_id = [company['id'] for company in contract['companies']]
        queries = [{'company_id': id} for id in contract_companies_id]
        director_role = mongo.find_one_document('role', {'name': 'director'})
        director_role_id = str(director_role['_id'])
        notification_recipients = []
        for employee in mongo.find_documents_under_operator('employee', 'or', queries):
            notification_recipient = {'id': str(employee['_id']), 'email': employee['email']}
            if notification_type == 'signing':
                if employee['role_id'] == director_role_id:
                    notification_recipients.append(notification_recipient)
            else:
                if notification_recipient['id'] != employee_id:
                    notification_recipients.append(notification_recipient)
        create_notifications(contract_id, notification_recipients, notification_type)
    if action_on_status == 'Harmonize':
        mongo.delete_many_documents('comment', {'contract_id': contract_id})
    return jsonify('Updated')


@app.route('/comment/create', methods=['POST'])
def create_comment():
    contract_id, contract_text, author, text, number = request.json['contractId'], request.json['contractText'], \
                                                       request.json['userName'], request.json['text'], \
                                                       request.json['number']
    comment = {'contract_id': contract_id, 'number': number,
               'related_comments': [{'id': 0, 'author': author, 'text': text,
                                     'creation_date': datetime.now().strftime('%d.%m.%y %H:%M:%S')}]
               }
    mongo.insert_one_document('comment', comment)
    contract = mongo.find_one_document('contract', {'_id': ObjectId(contract_id)})
    contract['text'] = contract_text
    mongo.update_one_document('contract', contract_id, contract)
    return jsonify('Created'), 201


@app.route('/contract/create', methods=['POST'])
def create_contract():
    text, companies = request.json['text'], request.json['companies']
    document = {
        'text': text, 'companies': companies,
        'creation_date': datetime.now().strftime('%d.%m.%y %H:%M:%S'), 'status': utils.create_initial_status(companies)
        }
    inserted_id = mongo.insert_one_document('contract', document) or False
    return jsonify(inserted_id), 201


@app.route('/dialog/create', methods=['POST'])
def create_dialog():
    data = request.json
    contract_id, user_id, user_name, message_text, recipient = \
        data['contractId'], data['userId'], data['userName'], data['messageText'], data['recipient']
    if recipient == 'everybody':
        contract = mongo.find_one_document('contract', {'_id': ObjectId(contract_id)})
        participants = []
        for company in contract['companies']:
            company_employees = mongo.find_documents('employee', {'company_id': company['id']})
            participants.extend(list(company_employees))
    else:
        queries = [{'_id': ObjectId(id)} for id in [user_id, recipient]]
        participants = mongo.find_documents_under_operator('employee', 'or', queries)
    dialog_participants = []
    for participant in participants:
        participant_entities = {'id': str(participant['_id']), 'name': participant['name']}
        dialog_participants.append(participant_entities)
    dialog = {'contract_id': contract_id, 'participants': dialog_participants}
    dialog_id = mongo.insert_one_document('dialog', dialog)
    message_sender = {'id': user_id, 'name': user_name}
    dialog_participants.remove(message_sender)
    is_read = {participant['id']: False for participant in dialog_participants}
    message = {'dialog_id': dialog_id, 'text': message_text, 'sender': message_sender,
               'is_read': is_read, 'creation_date': datetime.now().strftime('%d.%m.%y %H:%M:%S')}
    mongo.insert_one_document('message', message)
    return jsonify('Created'), 201


@app.route('/invitations/create', methods=['POST'])
def create_invitations():
    data = request.json
    contract_id, type, creator_id, recipients_company_id = \
        data['contractId'], data['reason'], data['senderId'], data['company']
    creator = mongo.find_one_document('employee', {'_id': ObjectId(creator_id)})
    creator_name, creator_company_id = creator['name'], creator['company_id']
    creator_company_name = mongo.find_one_document('company', {'_id': ObjectId(creator_company_id)})['name']
    recipients_company_name = mongo.find_one_document('company', {'_id': ObjectId(recipients_company_id)})['name']
    creation_date = datetime.now().strftime('%d.%m.%y %H:%M:%S')
    invitation = {
        'contract_id': contract_id, 'status': 'pending', 'creation_date': creation_date, 'type': type,
        'creator':
            {
                'id': creator_id, 'name': creator_name, 'company_id': creator_company_id,
                'company_name': creator_company_name
            },
        'recipient':
            {
                'id': '', 'name': '', 'company_id': recipients_company_id,
                'company_name': recipients_company_name
            },
    }
    if type == 'signing':
        director_role = mongo.find_one_document('role', {'name': 'director'})
        director_role_id = str(director_role['_id'])
        query = {'company_id': recipients_company_id, 'role_id': director_role_id}
        recipient = mongo.find_one_document('employee', query)
        recipient_id, recipient_name = str(recipient['_id']), recipient['name']
        invitation['recipient'].update({'id': recipient_id, 'name': recipient_name})
        mongo.insert_one_document('invitation', invitation)
        return jsonify('Created'), 201
    invitations = []
    invitation_recipients = mongo.find_documents('employee', {'company_id': recipients_company_id})
    notification_recipients = []
    for recipient in invitation_recipients:
        recipient_id, recipient_name, recipient_email = str(recipient['_id']), recipient['name'], recipient['email']
        invitation_copy = copy.deepcopy(invitation)
        invitation_copy['recipient'].update({'id': recipient_id, 'name': recipient_name})
        invitations.append(invitation_copy)
        notification_recipients.append({'id': recipient_id, 'email': recipient_email})
    mongo.insert_documents('invitation', invitations)
    if type == 'editing':
        create_notifications(contract_id, notification_recipients, 'editing')
    return jsonify('Created'), 201


@app.route('/message/create', methods=['POST'])
def create_message():
    dialog_id, text, sender_id, sender_name = request.json['dialogId'], request.json['messageText'], \
                                              request.json['sender']['id'], request.json['sender']['name']
    dialog = mongo.find_one_document('dialog', {'_id': ObjectId(dialog_id)})
    is_read = {participant['id']: False for participant in dialog['participants'] if participant['id'] != sender_id}
    message = {'dialog_id': dialog_id, 'text': text, 'sender': {'id': sender_id, 'name': sender_name},
               'is_read': is_read, 'creation_date': datetime.now().strftime('%d.%m.%y %H:%M:%S')}
    mongo.insert_one_document('message', message)
    return jsonify('Created'), 201


@app.route('/comment/update', methods=['PUT'])
def update_comment():
    contract_id, author, number, text = request.json['contractId'], request.json['userName'], \
                                        request.json['commentNumber'], request.json['responseText']
    comment = mongo.find_one_document('comment', {'contract_id': contract_id, 'number': number})
    ids = [related_comment['id'] for related_comment in comment['related_comments']]
    id = max(*ids) + 1 if len(ids) > 1 else ids[0] + 1
    new_related_comment = {'id': id, 'author': author, 'text': text,
                           'creation_date': datetime.now().strftime('%d.%m.%y %H:%M:%S')}
    comment['related_comments'].append(new_related_comment)
    mongo.update_one_document('comment', str(comment['_id']), comment)
    return jsonify('Updated')


@app.route('/contract/update', methods=['PUT'])
def update_contract():
    contract_id, new_text = request.json['id'], request.json['text']
    contract = mongo.find_one_document('contract', {'_id': ObjectId(contract_id)})
    contract = json.loads(utils.convert_mongo_data_to_json(contract))
    del contract['_id']
    contract['text'] = new_text
    if not request.json.get('onlyText'):
        types_map = {'harmonization': 'harmonization', 'harmonized': 'signing', 'signing': 'signing'}
        invitation_type_to_delete = types_map.get(contract['status']['name'])
        if invitation_type_to_delete:
            mongo.delete_many_documents('invitation', {'contract_id': contract_id, 'type': invitation_type_to_delete})
        mongo.delete_many_documents('comment', {'contract_id': contract_id})
        contract['status'] = utils.create_initial_status(contract['companies'])
    mongo.update_one_document('contract', contract_id, contract)
    return jsonify('Updated')


@app.route('/employees/roles/update', methods=['PUT'])
def update_employees_roles():
    for employee_info in request.json:
        employee_id, new_role = employee_info['employeeId'], employee_info['selectedRole']
        employee = mongo.find_one_document('employee', {'_id': ObjectId(employee_id)})
        employee['role_id'] = str(mongo.find_one_document('role', {'name': new_role})['_id'])
        mongo.update_one_document('employee', employee_id, employee)
    return jsonify('Updated')


@app.route('/comment/delete', methods=['DELETE'])
def delete_comment():
    contract_id, new_contract_text, number, id = request.json['contractId'], request.json['contractTextAfterRemoval'], \
                                                 request.json['number'], request.json['id']
    comment = mongo.find_one_document('comment', {'contract_id': contract_id, 'number': number})
    updated_related_comments = [comment for comment in comment['related_comments'] if comment['id'] != id]
    if updated_related_comments:
        comment['related_comments'] = updated_related_comments
        mongo.update_one_document('comment', str(comment['_id']), comment)
        return jsonify('Updated')
    mongo.delete_one_document('comment', {'contract_id': contract_id, 'number': number})
    contract = mongo.find_one_document('contract', {'_id': ObjectId(contract_id)})
    contract['text'] = new_contract_text
    mongo.update_one_document('contract', contract_id, contract)
    return jsonify('Deleted')


@app.route('/contract/delete/<contract_id>', methods=['DELETE'])
def delete_contract(contract_id):
    mongo.delete_one_document('contract', {'_id': ObjectId(contract_id)})
    mongo.delete_many_documents('comment', {'contract_id': contract_id})
    mongo.delete_many_documents('invitation', {'contract_id': contract_id})
    mongo.delete_many_documents('notification', {'contract_id': contract_id})
    mongo.delete_many_documents('version', {'contract_id': contract_id})
    dialogs = mongo.find_documents('dialog', {'contract_id': contract_id})
    dialogs_id = [str(dialog['_id']) for dialog in dialogs]
    mongo.delete_many_documents('dialog', {'contract_id': contract_id})
    mongo.delete_many_documents('message', {'dialog_id': {'$in': dialogs_id}})
    return jsonify('Deleted')


@app.route('/contract/version/delete/<version_id>', methods=['DELETE'])
def delete_contract_version(version_id):
    mongo.delete_one_document('version', {'_id': ObjectId(version_id)})
    return jsonify('Deleted')


def create_notifications(contract_id, notification_recipients: list, type):
    creation_date = datetime.now().strftime('%d.%m.%y %H:%M:%S')
    text_map = {
        'editing': 'Invitation to editing contract was received',
        'harmonization': 'Contract needs a harmonization for changing its status to "harmonized"',
        'signing': 'Contract is harmonized and needs to be signed for changing its status to "signed"',
        'archived': 'Contract is archived'
    }
    notification = {'contract_id': contract_id, 'creation_date': creation_date, 'is_read': False, 'type': type,
                    'text': text_map[type]}
    notifications = []
    recipient_emails = []
    for recipient in notification_recipients:
        notification_copy = notification.copy()
        notification_copy['recipient_id'] = recipient['id']
        notifications.append(notification_copy)
        recipient_emails.append(recipient['email'])
    mongo.insert_documents('notification', notifications)
    send_email_notification.delay(contract_id, text_map[type], recipient_emails)


if __name__ == '__main__':
    app.run(debug=True)
