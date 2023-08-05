from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import (
    UserMixin,
    login_user,
    LoginManager,
    current_user,
    logout_user,
    login_required,
)
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship
from sqlalchemy.exc import IntegrityError, NoResultFound
from functools import wraps
from os import environ

from forms import CreatePostForm, RegisterUserForm, LoginForm, CommentForm


app = Flask(__name__)
app.config["SECRET_KEY"] = generate_password_hash(
    str(environ.get("SECRET_KEY")), salt_length=10
)

ckeditor = CKEditor(app)
Bootstrap5(app)

login_manager = LoginManager()
login_manager.init_app(app)


# CONNECT TO DB
app.config["SQLALCHEMY_DATABASE_URI"] = environ.get("SQL_DB_URL")
db = SQLAlchemy()
db.init_app(app)

gravatar = Gravatar(
    app,
    size=100,
    rating="x",
)


# CONFIGURE TABLES
class User(UserMixin, db.Model):
    __tablename__ = "user_data"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)

    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user_data.id"))

    author = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="parent_post")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user_data.id"))
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))

    comment_author = relationship("User", back_populates="comments")
    parent_post = relationship("BlogPost", back_populates="comments")


with app.app_context():
    db.create_all()


def admin_only(func):
    @wraps(func)
    def wrapper_function(*args, **kwargs):
        if current_user.id == 1:  # type: ignore
            return func(*args, **kwargs)
        else:
            return abort(403)

    return wrapper_function


# A User Loader.
@login_manager.user_loader
def user_loader(user_id):
    return db.get_or_404(User, user_id)


@app.route("/register", methods=["POST", "GET"])
def register():
    form = RegisterUserForm()
    if form.validate_on_submit():
        try:
            user = User(
                name=form.data.get("name"),
                email=form.data.get("email"),
                password=generate_password_hash(
                    form.data.get("password"), salt_length=12
                ),
            )  # type: ignore

            db.session.add(user)
            db.session.commit()

        except IntegrityError:
            flash(
                "This email already exists in our database. Please Login to continue."
            )
            return redirect(url_for("login"))
        else:
            login_user(user)
            return redirect(url_for("get_all_posts"))

    return render_template("register.html", form=form, authenticated=current_user.is_authenticated)  # type: ignore


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = db.session.execute(
                db.select(User).where(User.email == form.data.get("email"))
            ).scalar_one()
        except NoResultFound:
            flash("This email does not exist in our database. Please Sign UP!")
            return redirect(url_for("register"))
        else:
            if check_password_hash(user.password, form.data.get("password")):
                login_user(user)
                return redirect(url_for("get_all_posts"))
            else:
                flash("Invalid password!!!")
                return redirect(url_for("login"))

    return render_template("login.html", form=form, authenticated=current_user.is_authenticated)  # type: ignore


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("get_all_posts"))


@app.route("/")
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()

    return render_template("index.html", all_posts=posts, authenticated=current_user.is_authenticated)  # type: ignore


@app.route("/post/<int:post_id>", methods=["POST", "GET"])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    form = CommentForm()
    if form.validate_on_submit():
        if current_user.is_authenticated:  # type: ignore
            comment = Comment(
                text=form.data.get("body"),
                comment_author=current_user,
                parent_post=requested_post,
            )
            db.session.add(comment)
            db.session.commit()
            return redirect(url_for("show_post", post_id=post_id))
        else:
            flash("First Login or Register in order to comment !")
            return redirect(url_for("login"))

    return render_template("post.html", post=requested_post, form=form, authenticated=current_user.is_authenticated)  # type: ignore


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y"),
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, authenticated=current_user.is_authenticated)  # type: ignore


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body,
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True, authenticated=current_user.is_authenticated)  # type: ignore


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for("get_all_posts"))


@app.route("/about")
def about():
    return render_template("about.html", authenticated=current_user.is_authenticated)  # type: ignore


@app.route("/contact")
def contact():
    return render_template("contact.html", authenticated=current_user.is_authenticated)  # type: ignore


if __name__ == "__main__":
    app.run(debug=True, port=5002)
