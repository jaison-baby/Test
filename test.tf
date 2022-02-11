provider "aws" {
access_key = ""
secret_key = ""
region = "us-east-2"
}

resource "aws_instance" "instance1" {
ami = "ami-0b614a5d911900a9b"
instance_type = "t2.micro"
tags = {
Name = "redhat"
}
}
