import bcrypt

salt = bcrypt.gensalt()
print(salt)