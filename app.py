from enum import unique

from click import Tuple
from flask import Flask, request, render_template, url_for, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import delete,text,func
from sqlalchemy.orm import DeclarativeBase
import requests
from bs4 import BeautifulSoup
from sqlalchemy.sql.functions import current_time

# （済）株リストのdbを作成
# （済）編集ボタンを追加し、編集できるようにする
# （済）年間配当をtopに表示
# （済）現在の配当をグラフで表示
# 株別の配当金を積み上げ形式でグラフに表示
# 増配率を自動で計算
# 増配率を加味した今後の予想配当金を計算
# 今後の予想配当を棒グラフで表示
#　gitのテスト

URL = "https://kabutan.jp/stock/?code="

class Base(DeclarativeBase):
    pass

#Flaskアプリのインスタンスを作成
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///stock-list.db"
db = SQLAlchemy(app)

class Stock(db.Model):
    __tablename__ = "stocks"
    id = db.Column(db.Integer, primary_key=True)
    stock_number = db.Column(db.Integer,unique=True, nullable=False)
    company_name = db.Column(db.String(50), unique=True, nullable=False)
    purchased_price = db.Column(db.Float, nullable=False)
    shares = db.Column(db.Integer, nullable=False)
    dividend_yield = db.Column(db.Float, nullable=False)
    dividend = db.Column(db.Float, nullable=False)
    current_price = db.Column(db.Float, nullable=False)
    gain_loss = db.Column(db.Float, nullable=False)

with app.app_context():
    db.create_all()

@app.route("/", methods=["GET", "POST"])
def index():
    # db.session.expire_all()
    stocks = db.session.execute(db.select(Stock).order_by(Stock.stock_number)).scalars()
    annual_dividend = db.session.query(func.sum(Stock.dividend)).scalar()
    if annual_dividend == None:
        annual_dividend = 0
    company_names = []
    dividends = []
    for stock in stocks:
        company_names.append(stock.company_name)
        dividends.append(stock.dividend)
    print(company_names)
    print(dividends)
    return render_template("index.html", stocks=stocks, annual_dividend=annual_dividend, company_names=company_names, dividends=dividends)

@app.route("/add_stock", methods=["GET", "POST"])
def add_stock():
    if request.method == "POST":
        stock_number = int(request.form["stock_number"])
        purchased_price = float(request.form["purchased_price"])
        shares = int(request.form["shares"])

        url = URL + str(stock_number)
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        company_name = soup.find(name="h2").text.split()[1]
        current_price = int(float(soup.find("span", class_="kabuka").text.replace(",", "").replace("円", "")))
        dividend_scraping = soup.select("#stockinfo_i3 > table > tbody > tr:nth-child(1) > td:nth-child(3)")[0].text.replace("％", "")
        if dividend_scraping == "－":
            dividend_yield = 0
        else:
            dividend_yield = float(dividend_scraping) / 100

        stock = db.session.execute(db.select(Stock).where(Stock.company_name == company_name)).scalar()

        if stock:
            print("ある")
            stock.shares += shares
            stock.dividend_yield = dividend_yield
            stock.current_price = current_price
            stock.dividend = stock.shares * dividend_yield * current_price
            stock.gain_loss = (current_price - purchased_price) * shares
            db.session.commit()
        else:
            print("ない")
            stock = Stock(
                stock_number = stock_number,
                company_name = company_name,
                purchased_price = purchased_price,
                shares = shares,
                dividend_yield = dividend_yield,
                dividend = shares * dividend_yield * current_price,
                current_price = current_price,
                gain_loss = (current_price - purchased_price) * shares
            )
            db.session.add(stock)
            db.session.commit()

        return render_template("result.html", gain_loss=stock.gain_loss, dividend=stock.dividend, stock_number=stock_number, company_name=company_name)
    return render_template("add_stock.html")

@app.route("/modify", methods=["GET", "POST"])
def edit():
    if request.method == "POST":
        stock_id = request.form["id"]
        stock_to_update = db.get_or_404(Stock, stock_id)
        stock_to_update.purchased_price = float(request.form["purchased_price"])
        stock_to_update.shares = int(request.form["shares"])

        url = URL + str(stock_to_update.stock_number)
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        stock_to_update.current_price = int(float(soup.find("span", class_="kabuka").text.replace(",", "").replace("円", "")))
        dividend_scraping = soup.select("#stockinfo_i3 > table > tbody > tr:nth-child(1) > td:nth-child(3)")[0].text.replace("％", "")
        if dividend_scraping == "－":
            stock_to_update.dividend_yield = 0
        else:
            stock_to_update.dividend_yield = float(dividend_scraping) / 100

        stock_to_update.dividend = stock_to_update.shares * stock_to_update.dividend_yield * stock_to_update.current_price
        stock_to_update.gain_loss = (stock_to_update.current_price - stock_to_update.purchased_price) * stock_to_update.shares
        db.session.commit()
        return redirect(url_for("index"))
    stock_id = request.args.get("id")
    stock_selected = db.get_or_404(Stock, stock_id)
    return render_template("edit.html", stock=stock_selected)


if __name__ == "__main__":
    app.run(debug=True, port=5000)