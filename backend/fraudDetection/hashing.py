from passlib.context import CryptContext
import bcrypt


class Hash():
    def hash(password):
        pwd_cxt = CryptContext(schemes=["bcrypt"],deprecated="auto")

        return  pwd_cxt.hash(password)
    
    def  verify(plain_password,hash_password):
        pwd_cxt = CryptContext(schemes=["bcrypt"],deprecated="auto")

        return pwd_cxt.verify(plain_password,hash_password)
    


    

