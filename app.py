import os
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_super_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///market.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER) 
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

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
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='vendor')

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
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    price_per_day = db.Column(db.Float, nullable=False)
    bookings = db.relationship('Booking', backref='stall', lazy=True)

    def __repr__(self):
        return f'<Stall {self.name}>'

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vendor_name = db.Column(db.String(100), nullable=False)
    vendor_phone = db.Column(db.String(20), nullable=False)
    vendor_email = db.Column(db.String(100), nullable=True) 
    stall_id = db.Column(db.Integer, db.ForeignKey('stall.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    booked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    payment_proof_url = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f'<Booking {self.id} - {self.vendor_name} for Stall {self.stall.name}>'

@app.route('/')
def index():
    today = date.today()
    stalls = Stall.query.all()
    stalls_with_status = []
    
    for stall in stalls:
        # ค้นหาการจองทั้งหมดที่เกี่ยวข้องกับแผงในวันนี้
        all_bookings = Booking.query.filter(
            Booking.stall_id == stall.id,
            Booking.start_date <= today,
            Booking.end_date >= today
        ).all()

        # กำหนดสถานะเริ่มต้นเป็น 'ว่าง'
        status = 'ว่าง'
        
        # ลูปผ่านการจองทั้งหมดเพื่อตรวจสอบสถานะ
        for booking in all_bookings:
            if booking.status == 'approved':
                status = 'ไม่ว่าง'
                break  # ถ้าเจอการจองที่อนุมัติแล้ว ไม่ต้องตรวจสอบการจองอื่นอีก
            elif booking.status in ['pending', 'pending_verification']:
                status = 'รอการอนุมัติ'
                # ไม่ต้อง break เพราะอาจมีสถานะ approved ตามมาใน booking อื่น
        
        stalls_with_status.append({'stall': stall, 'status': status})
        
    return render_template(
        'index.html', 
        stalls_with_status=stalls_with_status
    )
@app.route('/book/<int:stall_id>', methods=['GET', 'POST']) 
def book_stall(stall_id): 
    stall = Stall.query.get_or_404(stall_id) 
    today = date.today() 
     
    # แก้ไขโค้ดส่วนนี้ให้ตรวจสอบเฉพาะสถานะ 'approved' เท่านั้น
    today_booking = Booking.query.filter( 
        Booking.stall_id == stall_id, 
        Booking.start_date <= today, 
        Booking.end_date >= today,
        Booking.status == 'approved'
    ).first() 

    if request.method == 'POST': 
        vendor_name = request.form.get('vendor_name') 
        vendor_phone = request.form.get('vendor_phone') 
        vendor_email = request.form.get('vendor_email') 
         
        start_date = today 
        end_date = today 

        try: 
            if today_booking: 
                flash('แผงตลาดนี้ถูกจองแล้วสำหรับวันนี้', 'danger') 
                return redirect(url_for('index')) 
             
            new_booking = Booking( 
                vendor_name=vendor_name, 
                vendor_phone=vendor_phone, 
                vendor_email=vendor_email, 
                stall_id=stall_id, 
                start_date=start_date, 
                end_date=end_date, 
                total_price=stall.price_per_day, 
                status="pending" 
            ) 
             
            db.session.add(new_booking) 
            db.session.commit() 
             
            flash('การจองสำเร็จ! กรุณารอการตรวจสอบจากผู้ดูแล', 'success') 
            return redirect(url_for('index')) 
         
        except Exception as e: 
            db.session.rollback() 
            flash(f'เกิดข้อผิดพลาดในการจอง: {str(e)}', 'danger') 
            return redirect(url_for('book_stall', stall_id=stall_id)) 
     
    return render_template('book.html', stall=stall, today_booking=today_booking)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('เข้าสู่ระบบสำเร็จ!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
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

    if new_status in ['approved', 'rejected'] and booking.status in ['pending', 'pending_verification']:
        booking.status = new_status
        try:
            db.session.commit()
            flash(f'อัปเดตสถานะการจอง #{booking.id} เป็น "{new_status}" เรียบร้อยแล้ว', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'เกิดข้อผิดพลาดในการอัปเดตสถานะ: {e}', 'danger')
    else:
        flash('สถานะการจองไม่ถูกต้อง หรือคุณไม่สามารถอนุมัติได้', 'danger')

    return redirect(url_for('admin_dashboard'))

@app.route('/pay/<int:booking_id>', methods=['GET', 'POST'])
@admin_required
def pay_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)

    if request.method == 'POST':
        if booking.status in ['approved', 'pending']:
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

#@app.route('/admin/booking/<int:booking_id>/cancel', methods=['POST'])
#@admin_required
#def cancel_booking(booking_id):
 #   booking = Booking.query.get_or_404(booking_id)

  #  if booking.status in ['confirmed', 'pending', 'paid']:
   #     booking.status = 'cancelled'
    #    try:
     #       db.session.commit()
      #      flash(f'การจอง #{booking.id} ถูกยกเลิกเรียบร้อยแล้ว', 'success')
       # except Exception as e:
        #    db.session.rollback()
         #   flash(f'เกิดข้อผิดพลาดในการยกเลิกการจอง: {e}', 'danger')
   # else:
    #    flash('ไม่สามารถยกเลิกการจองที่มีสถานะนี้ได้', 'danger')

   # return redirect(url_for('admin_dashboard'))

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