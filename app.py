from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3, uuid, traceback
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Attr

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
users = dynamodb.Table('Users')
todos = dynamodb.Table('Todos')


reset_tokens = {}

@app.route('/register_user', methods=['POST'])
def register_user():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        email = data.get('email')

        if not username or not password or not email:
            return jsonify({'status': 'fail', 'message': 'Missing fields'}), 400

        result = users.get_item(Key={'username': username})
        if 'Item' in result:
            return jsonify({'status': 'fail', 'message': 'User already exists'}), 409

        users.put_item(Item={'username': username, 'password': password, 'email': email})
        return jsonify({'status': 'success', 'message': 'Registered successfully'}), 200
    except Exception as e:
        print("ERROR in /register_user:", e)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/login', methods=['POST', 'OPTIONS'])
def login_user():
    if request.method == 'OPTIONS':
        return '', 200

    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    result = users.get_item(Key={'username': username})
    user = result.get('Item')

    if user:
        if user['password'] == password:
            return jsonify({"status": "success"}), 200
        else:
            return jsonify({"status": "fail", "message": "Incorrect password"}), 401
    else:
        return jsonify({"status": "fail", "message": "User not found"}), 404

@app.route('/todos', methods=['POST'])
def add_todo():
    try:
        data = request.get_json()
        todo_id = str(uuid.uuid4())
        todos.put_item(Item={
            'todoId': todo_id,
            'username': data['username'],
            'task': data['task'],
            'status': 'pending'
        })
        return jsonify({"status": "success", "id": todo_id})
    except Exception as e:
        print("ERROR in /todos POST:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/todos', methods=['GET'])
def get_todos():
    username = request.args.get('username')
    if not username:
        return jsonify({'status': 'fail', 'message': 'Username is required'}), 400

    try:
        response = todos.scan()
        items = [item for item in response['Items'] if item['username'] == username]
        return jsonify(items)
    except Exception as e:
        print("ERROR in /todos GET:", e)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/todos/<todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    try:
        todos.delete_item(Key={'todoId': todo_id})
        return jsonify({"status": "deleted"})
    except Exception as e:
        print("ERROR in /todos DELETE:", e)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/todos/<todo_id>/toggle', methods=['PUT'])
def toggle_todo(todo_id):
    try:
        item = todos.get_item(Key={'todoId': todo_id})['Item']
        new_status = 'completed' if item['status'] == 'pending' else 'pending'
        todos.update_item(
            Key={'todoId': todo_id},
            UpdateExpression='SET #s = :val1',
            ExpressionAttributeValues={':val1': new_status},
            ExpressionAttributeNames={'#s': 'status'}
        )
        return jsonify({"status": "toggled", "new": new_status})
    except Exception as e:
        print("ERROR in /todos TOGGLE:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/todos/<todo_id>', methods=['PUT'])
def update_todo_text(todo_id):
    try:
        data = request.get_json()
        new_task = data.get('task')
        if not new_task:
            return jsonify({'status': 'fail', 'message': 'Task content missing'}), 400

        todos.update_item(
            Key={'todoId': todo_id},
            UpdateExpression='SET task = :val1',
            ExpressionAttributeValues={':val1': new_task}
        )
        return jsonify({'status': 'success'})
    except Exception as e:
        print("ERROR in /todos PUT:", e)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/reset-request', methods=['POST', 'OPTIONS'])
def reset_request():
    if request.method == 'OPTIONS':
        return '', 200

    try:
        data = request.get_json(force=True)
        email = data.get('email')  

        if not email:
            return jsonify({'message': 'Email is required'}), 400

        response = users.scan(
            FilterExpression=Attr('email').eq(email)
        )
        items = response.get('Items')

        if not items:
            return jsonify({'message': 'User with this email not found'}), 404

        username = items[0]['username']
        token = str(uuid.uuid4())
        reset_tokens[token] = username

        print("✅ Reset link:", f"http://localhost:5000/reset-password/{token}")
        return jsonify({'message': 'Reset link generated. Check terminal.'}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'message': f'Server error: {str(e)}'}), 500

@app.route('/users', methods=['GET'])
def get_all_users():
    try:
        response = users.scan()
        return jsonify(response['Items']), 200
    except Exception as e:
        print("ERROR in /users:", e)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.before_request
def log_routes_once():
    if not hasattr(app, 'routes_logged'):
        print("📌 Registered Routes:")
        for rule in app.url_map.iter_rules():
            print(rule)
        app.routes_logged = True


@app.route('/', methods=['GET'])
def show_registered_users():
    try:
        response = users.scan()
        users_list = response.get('Items', [])
        return jsonify(users_list), 200  # This returns raw JSON
    except Exception as e:
        return jsonify({'error': str(e)}), 500





if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


