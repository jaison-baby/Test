from database import db

class tbl_events(db.Model):
	event_id=db.Column(db.String(100),primary_key=True)
	start_time=db.Column(db.DateTime,nullable=False)
	activity=db.Column(db.String(60))
	activity_description=db.Column(db.String(200))
	event_status=db.Column(db.String(60),default="INPROGRESS")
	last_updated_time=db.Column(db.DateTime,nullable=False)

class tbl_eip_mappings(db.Model):
	eip_id=db.Column(db.Integer ,primary_key=True)
	eip=db.Column(db.String(50), unique=True)
	attached_instance = db.Column(db.String(100),nullable=True)
	origin_domain=db.Column(db.String(100),nullable=False)
	playback_domain=db.Column(db.String(100),nullable=False)
	status=db.Column(db.String(60),default="DETACHED")
	attach_eventid=db.Column(db.String(100),nullable=True)
	detach_eventid=db.Column(db.String(100),db.ForeignKey("tbl_events.event_id"),nullable=True)
	last_updated_time=db.Column(db.DateTime,nullable=True)
	is_protected=db.Column(db.Boolean,default=False)

class tbl_instance(db.Model):
	instance_id=db.Column(db.String(100),primary_key=True)
	event_id=db.Column(db.String(100),db.ForeignKey("tbl_events.event_id"),nullable=False)
	privateip=db.Column(db.String(60),default=0)
	public_ip=db.Column(db.String(60),default=0)
	launch_time=db.Column(db.DateTime,nullable=False)
	status=db.Column(db.String(60),default=0)
	status_updated_time=db.Column(db.DateTime,nullable=True)
	active_connections=db.Column(db.Integer,default=0)
	load_avg=db.Column(db.String(60),default=0)
	last_updated_time=db.Column(db.DateTime,nullable=True)
	priority=db.Column(db.Integer)

class tbl_event_logs(db.Model):
    log_id=db.Column(db.Integer ,primary_key=True)
    event_id=db.Column(db.String(100),db.ForeignKey("tbl_events.event_id"),nullable=False)
    last_updated_time=db.Column(db.DateTime,nullable=False)
    event_description=db.Column(db.String(200))
    event_log=db.Column(db.String(200))


class tbl_instance_logs(db.Model):
    log_id=db.Column(db.Integer,primary_key=True)
    instance_id = db.Column(db.String(100),default=0)
    event_id=db.Column(db.String(100),db.ForeignKey("tbl_events.event_id"),nullable=False)
    privateip=db.Column(db.String(60),default=0)
    last_updated_time=db.Column(db.DateTime,nullable=False)
    instance_log=db.Column(db.String(200))
    eip=db.Column(db.String(50))

class tbl_mail_alerts(db.Model):
	mail_id=db.Column(db.Integer,primary_key=True)
	instance_id = db.Column(db.String(100),nullable=True)
	last_mail_alert_time=db.Column(db.DateTime,nullable=True)
