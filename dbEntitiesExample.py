company = {'id': 1, 'name': 'Green'}
role = {'name': 'lawyer'} # lawyer or economist or director
employee = {'name': 'Yura Kotov', 'company_id': 1, 'role_id': 2}
contract = {'text': 'some text', 'creation_date': '1.1.2021', 'companies': [{'id': 1, 'name': 'Zila'}, {'id': 2, 'name': 'ABC'}],
            'status': {'name': 'creating',
                       'companies': {
                           'id_1': {'lawyer': True,
                                    'economist': False,
                                    'director': False,},
                           'id_2': {'lawyer': True,
                                    'economist': False,
                                    'director': True,},
                       }
                      },
            }
invitation = {'contract_id': 1, 'creator': {'id': 1, 'name': 'Liza Kotova', 'company_id': '', 'company_name': 'Zesla Group'}, 'recipient':
    {'id': 2, 'name': 'Lex Wom', 'company_id': '', 'company_name': 'BMW'}, 'type': 'editing', 'status': 'accepted', 'creation_date': '05.03.21 23:19'}
notification = {'contract_id': '1', 'recipient_id': 1, 'creation_date': '05.03.21 23:19', 'is_read': False,
                'type': 'editing', 'text': 'Invitation to editing contract was received'}
dialog = {'contract_id': '1',
          'participants': [{'id': '1', 'name': 'Gustavo'}, {'id': '2', 'name': 'Sonya'}] }
message = {'dialog_id': 1, 'sender': {'id': '1', 'name': 'Gustavo'},
           'text': 'some text', 'is_read': {'2': False}, 'creation_date': '1.1.2021'}
version = {'contract_id': '1', 'creator_id': 1, 'text': 'some text', 'creation_date': '05.03.21 23:19', 'contract_status': 'created'}
comment = {'contract_id': '1', 'number': 0,
    'related_comments': [
                    {'id': 0, 'author': 'Danya Nagiev', 'text': 'My comment', 'creation_date': '05.03.21 23:19:20'},
                    {'id': 1, 'author': 'Vasya2', 'text': 'My comment2', 'creation_date': '06.03.21 04:20:54'}
                ],
            }


# insert_documents('comment', [
#     {'contract_id': '60b6b045e28f62f52584e84f', 'number': 2,
#      'related_comments': [
#          {'id': 1, 'author': 'Danya Nagiev', 'text': 'My comment2', 'creation_date': '07.03.21 04:20:58'},
#          {'id': 0, 'author': 'Danya Nagiev', 'text': 'My comment', 'creation_date': '07.03.21 23:19:20'},
#      ],}
# ])

# insert_documents('role', [
#     {'name': 'lawyer'},
#     {'name': 'economist'},
#     {'name': 'director'},
# ])

# insert_documents('company', [
#     {'name': 'Zesla Group'},
#     {'name': 'ABC'},
#     {'name': 'BMW'},
# ])

# insert_documents('employee', [
#     {'name': 'Liza Kotova', 'company_id': '60a2778f6a4af06544b90cb1', 'role_id': '60a276765c6552ed06e294a3'},
#     {'name': 'Erik Gotov', 'company_id': '60a2778f6a4af06544b90cb1', 'role_id': '60a276765c6552ed06e294a4'},
#     {'name': 'Danya Nagiev', 'company_id': '60a2778f6a4af06544b90cb1', 'role_id': '60a276765c6552ed06e294a5'},
#     {'name': 'Lera Nord', 'company_id': '60a2778f6a4af06544b90cb2', 'role_id': '60a276765c6552ed06e294a3'},
#     {'name': 'Edik Child', 'company_id': '60a2778f6a4af06544b90cb2', 'role_id': '60a276765c6552ed06e294a4'},
#     {'name': 'Dmitry Gogol', 'company_id': '60a2778f6a4af06544b90cb2', 'role_id': '60a276765c6552ed06e294a5'},
#     {'name': 'Lex Wom', 'company_id': '60a2778f6a4af06544b90cb3', 'role_id': '60a276765c6552ed06e294a3'},
#     {'name': 'Emelya Restolov', 'company_id': '60a2778f6a4af06544b90cb3', 'role_id': '60a276765c6552ed06e294a4'},
#     {'name': 'Denis Kogol', 'company_id': '60a2778f6a4af06544b90cb3', 'role_id': '60a276765c6552ed06e294a5'}
# ])
