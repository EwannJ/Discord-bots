from subprocess import Popen

bot1 = Popen(["python3", "TSSE.py"])
print("Accès TSSE.py via main.py OK.")

bot2 = Popen(["python3", "Voltaire.py"])
print("Accès Voltaire.py via main.py OK.")

bot3 = Popen(["python3", "skr.py"])
print("Accès skr.py via main.py OK.")

bot1.wait()
bot2.wait()
bot3.wait()