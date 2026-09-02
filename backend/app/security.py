import os, jwt
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from .database import db_session
from .models import User, AuditEvent
pwd=PasswordHash.recommended(); bearer=HTTPBearer(); SECRET=os.getenv('JWT_SECRET','unsafe-development-secret')
def hash_password(v): return pwd.hash(v)
def verify_password(v,h): return pwd.verify(v,h)
def token_for(user): return jwt.encode({'sub':user.id,'role':user.role,'exp':datetime.now(timezone.utc)+timedelta(hours=8)},SECRET,algorithm='HS256')
def current_user(c: HTTPAuthorizationCredentials=Depends(bearer), db:Session=Depends(db_session)):
    try: payload=jwt.decode(c.credentials,SECRET,algorithms=['HS256']); user=db.get(User,payload['sub'])
    except Exception: user=None
    if not user: raise HTTPException(401,'Invalid or expired session')
    return user
def role(*allowed):
    def check(user=Depends(current_user)):
        if user.role not in allowed: raise HTTPException(403,'Insufficient permission')
        return user
    return check
def audit(db, actor, event, entity, entity_id, success=True, metadata=None): db.add(AuditEvent(actor_id=getattr(actor,'id',None),actor_role=getattr(actor,'role',None),event_type=event,entity_type=entity,entity_id=entity_id,success=success,metadata_=metadata))
