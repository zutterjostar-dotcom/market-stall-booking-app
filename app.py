from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
#from datetime import datetime
import datetime
import os
from functools import wraps
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
#from datetime import date
from flask_login import current_user
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user


app = Flask(__name__)

app.config['SECRET_KEY'] = 'your_super_secret_key_here'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER) 
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('กรุณาเข้าสู่ระบบด้วยบัญชี Admin เพื่อเข้าถึงหน้านี้', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False) 
    role = db.Column(db.String(20), nullable=False, default='admin')

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'

class Stall(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    price_per_day = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)

    
    bookings = db.relationship('Booking', backref='stall', lazy=True)

    def __repr__(self):
        return f'<Stall {self.name}>'

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vendor_name = db.Column(db.String(100), nullable=False)
    vendor_phone = db.Column(db.String(20), nullable=False)
    vendor_email = db.Column(db.String(100), nullable=True)
    image_url = db.Column(db.String(255), nullable=True) 
    status = db.Column(db.String(20), default='pending', nullable=False)
    stall_id = db.Column(db.Integer, db.ForeignKey('stall.id'), nullable=False)
    payment_proof_url = db.Column(db.String(255), nullable=True)

    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='confirmed')
    booked_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Booking {self.id} - {self.vendor_name} for Stall {self.stall.name}>'

from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or session.get('role') != 'admin':
            flash('กรุณาเข้าสู่ระบบด้วยบัญชี Admin เพื่อเข้าถึงหน้านี้', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

from datetime import date

# โค้ดส่วนอื่นๆ
from datetime import datetime

# ...
# โค้ดส่วนอื่นๆ

@app.route('/')
def index():
    today = datetime.date.today()
    stalls = Stall.query.all()
    stalls_with_status = []
    for stall in stalls:
        # ตรวจสอบการจองในวันปัจจุบัน
        booking = Booking.query.filter_by(
            stall_id=stall.id,
            start_date=today,
            end_date=today
        ).first()

        status = 'available'
        if booking:
            if booking.status == 'approved':
                status = 'occupied'
            elif booking.status == 'pending':
                status = 'pending'
            else:
                status = 'occupied'

        stalls_with_status.append({'stall': stall, 'status': status})
        
    return render_template(
        'index.html', 
        stalls_with_status=stalls_with_status
    )

# โค้ดส่วนอื่นๆ ที่เกี่ยวข้องกับการจองแผง
@app.route('/book/<int:stall_id>', methods=['GET', 'POST'])
def book_stall(stall_id):
    stall = Stall.query.get_or_404(stall_id)
    today = datetime.date.today()
    
    # ดึงข้อมูลการจองสำหรับวันนี้
    today_booking = Booking.query.filter_by(
        stall_id=stall_id,
        start_date=today,
        end_date=today
    ).first()

    if request.method == 'POST':
        vendor_name = request.form.get('vendor_name')
        vendor_phone = request.form.get('vendor_phone')
        
        # ตั้งค่า start_date และ end_date เป็นวันปัจจุบันโดยอัตโนมัติ
        start_date = today
        end_date = today
        
        # กำหนดค่าเริ่มต้นสำหรับคอลัมน์ที่ไม่ได้รับข้อมูลจากฟอร์ม
        vendor_email = None # กำหนดเป็น None หรือค่าเริ่มต้นที่เหมาะสม
        total_price = stall.price_per_day
        image_proof_url = None

        try:
            # ตรวจสอบว่ามีข้อมูลการจองสำหรับวันนี้อยู่แล้วหรือไม่
            if today_booking:
                flash('แผงตลาดนี้ถูกจองแล้วสำหรับวันนี้', 'danger')
                return redirect(url_for('index'))
            
            # สร้างรายการจองใหม่
            new_booking = Booking(
                vendor_name=vendor_name,
                vendor_phone=vendor_phone,
                vendor_email=vendor_email,  # เพิ่ม field นี้
                stall_id=stall_id,
                start_date=start_date,
                end_date=end_date,
                status="pending",
                total_price=total_price,  # เพิ่ม field นี้
                payment_proof_url=image_proof_url # เพิ่ม field นี้
            )
            
            # เพิ่มการจองใหม่ลงในฐานข้อมูล
            db.session.add(new_booking)
            db.session.commit()
            
            # ส่งผู้ใช้ไปยังหน้ายืนยันการจอง
            flash('การจองสำเร็จ! กรุณารอการตรวจสอบจากผู้ดูแล', 'success')
            return redirect(url_for('index'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'เกิดข้อผิดพลาดในการจอง: {str(e)}', 'danger')
            return redirect(url_for('book_stall', stall_id=stall_id))
    
    # หากเป็น GET request ให้แสดงหน้า book.html
    return render_template('book.html', stall=stall, today_booking=today_booking)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and user.verify_password(password):
            login_user(user) # ใช้ login_user จาก Flask-Login
            flash('เข้าสู่ระบบสำเร็จ!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user() # ใช้ logout_user จาก Flask-Login
    flash('ออกจากระบบแล้ว', 'info')
    return redirect(url_for('index'))

@app.route('/booking/success/<int:booking_id>')
def booking_success(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    return render_template('success.html', booking=booking)

@app.route('/admin/booking/<int:booking_id>/status', methods=['POST'])
@admin_required
def update_booking_status(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    new_status = request.form.get('status')

    if new_status in ['confirmed', 'rejected']:
        booking.status = new_status
        try:
            db.session.commit()
            flash(f'อัปเดตสถานะการจอง #{booking.id} เป็น "{new_status}" เรียบร้อยแล้ว', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'เกิดข้อผิดพลาดในการอัปเดตสถานะ: {e}', 'danger')
    else:
        flash('สถานะไม่ถูกต้อง', 'danger')

    return redirect(url_for('admin_dashboard'))

@app.route('/pay/<int:booking_id>', methods=['GET', 'POST'])
@admin_required
def pay_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)

    if request.method == 'POST':
        if booking.status in ['confirmed', 'pending']:
            booking.status = 'paid'
            try:
                db.session.commit()
                flash(f'การจอง #{booking.id} ได้รับการชำระเงินเรียบร้อยแล้ว!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'เกิดข้อผิดพลาดในการบันทึกการชำระเงิน: {e}', 'danger')
        else:
            flash(f'สถานะการจอง #{booking.id} ไม่สามารถชำระเงินได้', 'danger')

        return redirect(url_for('admin_dashboard'))

    return render_template('pay.html', booking=booking)

@app.route('/admin')
@admin_required 
def admin_dashboard():
    bookings = Booking.query.order_by(Booking.booked_at.desc()).all()
    stalls = Stall.query.all()
    users = User.query.all()
    return render_template('admin_dashboard.html', bookings=bookings, stalls=stalls, users=users)

@app.route('/admin/stalls/add', methods=['GET', 'POST'])
@admin_required
def add_stall():
    if request.method == 'POST':
        name = request.form['name']
        price_per_day = request.form['price_per_day']
        description = request.form.get('description')

        new_stall = Stall(
            name=name,
            price_per_day=price_per_day,
            description=description
        )
        try:
            db.session.add(new_stall)
            db.session.commit()
            flash('เพิ่มแผงตลาดใหม่สำเร็จ', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'เกิดข้อผิดพลาดในการเพิ่มแผง: {e}', 'danger')

    return render_template('add_edit_stall.html')

@app.route('/admin/stalls/edit/<int:stall_id>', methods=['GET', 'POST'])
@admin_required
def edit_stall(stall_id):
    stall = Stall.query.get_or_404(stall_id)

    if request.method == 'POST':
        stall.name = request.form['name']
        stall.price_per_day = request.form['price_per_day']
        stall.description = request.form.get('description')

        try:
            db.session.commit()
            flash('แก้ไขข้อมูลแผงตลาดสำเร็จ', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'เกิดข้อผิดพลาดในการแก้ไขแผง: {e}', 'danger')

    return render_template('add_edit_stall.html', stall=stall)

@app.route('/admin/stalls/delete/<int:stall_id>', methods=['POST'])
@admin_required
def delete_stall(stall_id):
    stall = Stall.query.get_or_404(stall_id)

    if Booking.query.filter_by(stall_id=stall.id).first():
        flash('ไม่สามารถลบแผงที่มีรายการจองอยู่ได้', 'danger')
        return redirect(url_for('admin_dashboard'))

    try:
        db.session.delete(stall)
        db.session.commit()
        flash('ลบแผงตลาดสำเร็จ', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'เกิดข้อผิดพลาดในการลบแผง: {e}', 'danger')

    return redirect(url_for('admin_dashboard'))

@app.route('/payment/<int:booking_id>')
def payment(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    return render_template('payment.html', booking=booking)

@app.route('/upload-payment-proof/<int:booking_id>', methods=['POST'])
def upload_payment_proof(booking_id):
    booking = Booking.query.get_or_404(booking_id)

    if 'payment_proof' not in request.files:
        flash('ไม่พบไฟล์หลักฐานการชำระเงิน', 'danger')
        return redirect(url_for('payment', booking_id=booking.id))

    file = request.files['payment_proof']

    if file.filename == '':
        flash('ไม่ได้เลือกไฟล์', 'danger')
        return redirect(url_for('payment', booking_id=booking.id))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filename = f"payment_{booking.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        booking.payment_proof_url = url_for('static', filename=f'uploads/{filename}')
        booking.status = 'pending_verification'

        try:
            db.session.commit()
            flash('อัปโหลดหลักฐานการชำระเงินสำเร็จแล้ว! เจ้าหน้าที่จะทำการตรวจสอบและยืนยันการจองของคุณ', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'เกิดข้อผิดพลาดในการบันทึกข้อมูล: {e}', 'danger')

    else:
        flash('ประเภทไฟล์ไม่ถูกต้อง (อนุญาตเฉพาะ PNG, JPG, JPEG, GIF)', 'danger')

    return redirect(url_for('index'))

@app.route('/admin/booking/<int:booking_id>/cancel', methods=['POST'])
@admin_required
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)

    if booking.status in ['confirmed', 'pending', 'paid']:
        booking.status = 'cancelled'
        try:
            db.session.commit()
            flash(f'การจอง #{booking.id} ถูกยกเลิกเรียบร้อยแล้ว', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'เกิดข้อผิดพลาดในการยกเลิกการจอง: {e}', 'danger')
    else:
        flash('ไม่สามารถยกเลิกการจองที่มีสถานะนี้ได้', 'danger')

    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
     with app.app_context():
        db.create_all()
        db.session.query(User).delete()
        new_admin = User(username='admin', role='admin')
        new_admin.password = 'admin123'
        db.session.add(new_admin)
        db.session.query(Stall).delete()
        stall_price_per_day = 50.00
        default_description = "แผงตลาดมาตรฐาน เหมาะสำหรับสินค้าทั่วไป"
        stall_number = 1
        for row in range(1, 5):
            for lock in range(1, 9):
                stall_name = f'แผงที่ {stall_number}'
                new_stall = Stall(name=stall_name, price_per_day=stall_price_per_day, description=default_description)
                db.session.add(new_stall)
                stall_number += 1
        db.session.commit()
    #app.run(debug=True)#
