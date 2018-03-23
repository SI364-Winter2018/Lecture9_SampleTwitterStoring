## SI 364 - Fall 2017
## HW 4

## Import statements
import os
from flask import Flask, render_template, session, redirect, url_for, flash, request
from flask_script import Manager, Shell
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FileField, PasswordField, BooleanField, SelectMultipleField, ValidationError
from wtforms.validators import Required, Length, Email, Regexp, EqualTo
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, MigrateCommand

# Imports for login management
from flask_login import LoginManager, login_required, logout_user, login_user, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash


# Configure base directory of app
basedir = os.path.abspath(os.path.dirname(__file__))

# Application configurations
app = Flask(__name__)
app.debug = True
app.config['SECRET_KEY'] = 'hardtoguessstringfromsi364'

app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://localhost/twitter_sample_ex"
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Set up Flask debug stuff
manager = Manager(app)
db = SQLAlchemy(app) # For database use

## Set up Shell context so it's easy to use the shell to debug
def make_shell_context():
    return dict(app=app, db=db, Tweet=Tweet, User=User, Hashtag=Hashtag) ## Adding your models to this shell context function so you can use them in the shell
migrate = Migrate(app, db)
# Add function use to manager
manager.add_command("shell", Shell(make_context=make_shell_context))
manager.add_command('db', MigrateCommand)

# Login configurations setup
login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'login'
login_manager.init_app(app) # set up login manager


#########
######### Everything above this line is important/useful setup, not problem-solving.
#########

##### Set up Models #####

# Assoc table
Tweet_Hashtag = db.Table('Tweet_Hashtag', db.Column('tweet_id', db.Integer, db.ForeignKey('tweets.id')), db.Column('hashtag_id', db.Integer, db.ForeignKey('hashtags.id')))

# Tweet model
class Tweet(db.Model):
    __tablename__ = "tweets"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(285))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    hashtags = db.relationship('Hashtag', secondary=Tweet_Hashtag, backref=db.backref('tweets', lazy='dynamic'), lazy='dynamic') # Hashtag relationship many-to-many setup

    def __repr__(self):
        return "{} by Twitter User {}".format(self.text, self.user_id)

# - Tweet
## -- id (Primary Key)
## -- text (String, up to 285 chars)
## -- user_id (Integer, ID of user posted)

# Special model for users to log in
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, index=True)
    email = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    tweets = db.relationship('tweets',backref='User')

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

## DB load function
## Necessary for behind the scenes login manager that comes with flask_login capabilities! Won't run without this.
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id)) # returns User object or None

# Hashtag model
class Hashtag(db.Model):
    __tablename__ = "hashtags"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String, unique=True)

    def __repr__(self):
        return "{} {}".format(self.text, self.id)


##### Set up Forms #####
## -- tweet text
## -- the twitter username who should post it
## -- a list of comma-separated hashtags it should have

class TweetForm(FlaskForm):
    text = StringField('What should the tweet say?', validators= [Required()])
    #username = StringField('Who should post the tweet?', validators = [Required()])
    hashtags = StringField('What hashtags should be used?', validators=[Required()])
    submit = SubmitField('Submit')

class RegistrationForm(FlaskForm):
    email = StringField('Email:', validators=[Required(),Length(1,64),Email()])
    username = StringField('Username:',validators=[Required(),Length(1,64),Regexp('^[A-Za-z][A-Za-z0-9_.]*$',0,'Usernames must have only letters, numbers, dots or underscores')])
    password = PasswordField('Password:',validators=[Required(),EqualTo('password2',message="Passwords must match")])
    password2 = PasswordField("Confirm Password:",validators=[Required()])
    submit = SubmitField('Register User')

    #Additional checking methods for the form
    def validate_email(self,field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')

    def validate_username(self,field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already taken')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[Required(), Length(1,64), Email()])
    password = PasswordField('Password', validators=[Required()])
    remember_me = BooleanField('Keep me logged in')
    submit = SubmitField('Log In')


##### Helper functions
### For database additions / get_or_create functions
# (Some of this code written by Julia Locke. Thanks, Julia!)

def get_or_create_tweet(db_session, tweet_text, hashtag_list=[]):
    tweet = Tweet.query.filter_by(text=tweet_text, user_id=current_user.id).first()
    if tweet:
        return tweet
    else:
        tweet = Tweet(text=tweet_text,user_id=current_user.id)
        for ht in hashtag_list:
            hashtag = get_or_create_hashtag(db_session, ht)
            tweet.hashtags.append(hashtag)
        db_session.add(tweet)
        db_session.commit()
        return tweet

# get_or_create_user not necessary, because that's handled in registration!

def get_or_create_hashtag(db_session, ht):
    hashtag = db_session.query(Hashtag).filter_by(text=ht).first()
    if hashtag:
        return hashtag
    else:
        hashtag = Hashtag(text=ht)
        db_session.add(hashtag)
        db_session.commit()
    return hashtag


##### Set up Controllers (view functions) #####

## Error handling routes
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

## Main route

@app.route('/', methods=['GET', 'POST'])
def index():
    tweets = Tweet.query.all()
    num_tweets = len(tweets)
    form = TweetForm()
    if request.method == 'POST' and form.validate_on_submit():
        if db.session.query(Tweet).filter_by(user_id=current_user.id, text=form.text.data).first():
            flash("You've already saved a tweet with this text by this user!")
        hl = [x.strip().rstrip() for x in (form.hashtags.data).split(',')]
        get_or_create_tweet(db.session, form.text.data, hashtag_list=hl)
        return redirect(url_for('see_all_tweets'))
    return render_template('index.html', form=form, num_tweets=num_tweets)

@app.route('/all_tweets')
@login_required
def see_all_tweets():
    all_tweets = []
    tweets = Tweet.query.filter_by(user_id=current_user.id).all()
    for t in tweets:
        all_tweets.append((t.text, t.hashtags)) # You could also handle this by using the objects themselves in the template, but this way works as well!
    return render_template('all_tweets.html', all_tweets=all_tweets)

@app.route('/all_users')
def see_all_users():
    users = User.query.all()
    people = []
    for u in users:
        people.append((u.username, len(Tweet.query.filter_by(user_id=u.id).all())))
    return render_template('all_users.html', usernames=people)

if __name__ == '__main__':
    db.create_all()
    manager.run() # Run with this: python main_app.py runserver
