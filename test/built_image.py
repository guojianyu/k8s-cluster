# -*- coding: utf-8 -*-
# @Time    : 2018/11/9 9:19
# @Author  : 郭建宇
# @Email   : 276381225@qq.com
# @File    : built_image.py
# @Software: PyCharm
"""
#模糊匹配与项目相关的镜像
#docker tag 5db5f8471261 ouruser/sinatra:devel 重新修改镜像的标签信息
docker save -o /root/program_testing_image.tar  program_testing_image#打包镜像
打包的镜像文件在基础镜像内部
cat /proc/1/cgroup | grep 'docker/' | tail -1 | sed 's/^.*\///' | cut -c 1-12
容器内部获取容器id    目前旨在centos测试可以
echo $(docker inspect -f '{{.ID}} {{.Name}}' $(docker ps -q))#获取容器信息
docker cp $(docker inspect -f '{{.ID}}' $(docker ps -q)):/root/program_testing_image.tar /root/#将容器内的文件转移出来
"""
import sys
import os
import subprocess
import uuid
import time
import paramiko
from functools import wraps
from datetime import datetime


GENERATE_IMAGE_PATH="/mnt"  #本地存储项目生成镜像的根目录
MASTER_SAVE_PATH="/home"   #压缩文件传输到远程目标主机存放文件的根目录
tag = "latest"
def timethis(func):
    """
    时间装饰器，计算函数执行所消耗的时间
    :param func:
    :return:
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = datetime.now()
        result = func(*args, **kwargs)
        end = datetime.now()
        #print(func.__name__, end-start)
        return result
    return wrapper


class SSHManager:
    def __init__(self, host, usr, passwd):
        self._host = host
        self._usr = usr
        self._passwd = passwd
        self._ssh = None
        self._sftp = None
        self._sftp_connect()
        self._ssh_connect()

    def __del__(self):
        if self._ssh:
            self._ssh.close()
        if self._sftp:
            self._sftp.close()

    def _sftp_connect(self):
        try:
            transport = paramiko.Transport((self._host, 22))
            transport.connect(username=self._usr, password=self._passwd)
            self._sftp = paramiko.SFTPClient.from_transport(transport)
        except Exception as e:
            raise RuntimeError("sftp connect failed [%s]" % str(e))

    def _ssh_connect(self):
        try:
            # 创建ssh对象
            self._ssh = paramiko.SSHClient()
            # 允许连接不在know_hosts文件中的主机
            self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            # 连接服务器
            self._ssh.connect(hostname=self._host,
                              port=22,
                              username=self._usr,
                              password=self._passwd,
                              timeout=5)
        except Exception:
            raise RuntimeError("ssh connected to [host:%s, usr:%s, passwd:%s] failed" %
                               (self._host, self._usr, self._passwd))

    def ssh_exec_cmd(self, cmd, path='~'):
        """
        通过ssh连接到远程服务器，执行给定的命令
        :param cmd: 执行的命令
        :param path: 命令执行的目录
        :return: 返回结果
        """
        try:
            result = self._exec_command('cd ' + path + ';' + cmd)
            print(result)
            return result
        except Exception:
            raise RuntimeError('exec cmd [%s] failed' % cmd)

    def ssh_exec_shell(self, local_file, remote_file):
        """
        执行远程的sh脚本文件
        :param local_file: 本地shell文件
        :param remote_file: 远程shell文件
        :param exec_path: 执行目录
        :return:
        """
        try:
            self._check_remote_file(local_file, remote_file)

            #result = self._exec_command('chmod +x ' + remote_file + '; cd' + exec_path + ';/bin/bash ' + remote_file)
            #print('exec shell result: ', result)
        except Exception as e:
            raise RuntimeError('ssh exec shell failed [%s]' % str(e))


    @staticmethod
    def is_file_exist(file_name):
        try:
            with open(file_name, 'r'):
                return True
        except Exception as e:
            return False

    def _check_remote_file(self, local_file, remote_file):
        """
        检测远程的脚本文件和当前的脚本文件是否一致，如果不一致，则上传本地脚本文件
        :param local_file:
        :param remote_file:
        :return:
        """
        try:

            self._upload_file(local_file, remote_file)
        except Exception as e:
            raise RuntimeError("upload error [%s]" % str(e))

    @timethis
    def _upload_file(self, local_file, remote_file):
        """
        通过sftp上传本地文件到远程
        :param local_file:
        :param remote_file:
        :return:
        """
        try:
            self._sftp.put(local_file, remote_file)
        except Exception as e:
            raise RuntimeError('upload failed [%s]' % str(e))

    def _exec_command(self, cmd):
        """
        通过ssh执行远程命令
        :param cmd:
        :return:
        """
        try:
            stdin, stdout, stderr = self._ssh.exec_command(cmd)
            return stdout.read().decode()
        except Exception as e:
            raise RuntimeError('Exec command [%s] failed' % str(cmd))

def update_base_image(image_name,project_name,setting_name):#本地文件与git项目的配置文件对比发现不同则更新镜像
    if not os.path.isdir("/mnt/%s"%(project_name)):#存在项目目录
        create_project_dir = "mkdir /mnt/%s" % (project_name)
        save_setting = "cp %s /mnt/%s/" % (setting_name, project_name)
        run_cmd(create_project_dir)
        run_cmd(save_setting)
        return 0

    diff_opt="diff -bBi /mnt/%s/%s  %s"%(project_name,setting_name,setting_name)#对比忽略空格空行大小写不同
    flag = run_cmd(diff_opt)
    if flag:#配置文件修改需要更新镜像
        print("file diff")
        #调用更新镜像的dockerfile
        tmp_image_name =uuid.uuid1()
        create_update_image = "docker build -f Dockerfile_update -t %s ." % (tmp_image_name)#根据dockerfile 更新镜像，产生的镜像为随机名字
        save_update_image="docker save -o ./%s.tar %s"%(tmp_image_name) #将新生成的镜像打包
        remove_update_image="docker rmi %s %s"%(tmp_image_name,image_name)#将新景象与旧镜像删除
        load_update_image="docker load < %s.tar"%(tmp_image_name)#将镜像解压
        reduct_image_name="docker tag %s %s"%(tmp_image_name,image_name)#将新镜像修改为初始名字

        update_setting_file="/cp -rf %s /mnt/%s/%s"%(setting_name,project_name,setting_name)#更新完镜像之后，将本地配置文件更新
        #将配置文件更新
        return 1
    else:
        print("file same")
        return 0


def build_base_image(image_name,project_name,setting_name):
    filter = """docker images --format "{{.ID}}: {{.Repository}}" --filter=reference='%s'"""%(image_name)
    flag = run_cmd(filter)
    if flag:#存在基础镜像
        return 1
    else:#不存在，则创建
        #调用创建基础镜像的Dockerfile
        #将配置文件保存，用于更新镜像
        create_image="docker build -f Dockerfile -t %s ."%(image_name)
        print(create_image)
        create_project_dir="mkdir %s/%s"%(GENERATE_IMAGE_PATH,project_name)
        save_setting = "cp %s %s/%s/"%(setting_name,GENERATE_IMAGE_PATH,project_name)
        run_cmd(create_image)
        run_cmd(create_project_dir)
        run_cmd(save_setting)
        return 0

def run_cmd(cmd):  # 执行youtube下载视频的命令
    child = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
    child.wait()
    Returncode = child.stdout.read()
    return Returncode

def get_git_head(count=7):
    with open(".git/HEAD") as f:
        line = f.readline()
        print (line)
    return line.strip()[:count]

def save_images_file(project_name,project_images_filter="kubernetes/kubernetes-dashboard*:head"):#打包项目生成的镜像文件
    """
    :param save_images_filter: 需要打包的镜像规则
    :return:
    """
    docker_rm_none = """docker rmi $(docker images | grep "none" | awk '{print $3}')"""  # 删除none镜像
    run_cmd(docker_rm_none)
    run_cmd("mkdir %s/%s" % (GENERATE_IMAGE_PATH,project_name))
    run_cmd("rm -rf %s/%s/*.tar"%(GENERATE_IMAGE_PATH,project_name)) #删除所有压缩文件
    docker_matching_image = """docker images --format "{{.ID}}:{{.Repository}}:{{.Tag}}"| grep -w %s"""%(project_images_filter)
    docker_images = run_cmd(docker_matching_image)
    images_list = docker_images.split("\n")
    if len(images_list) <=1:
        raise RuntimeError('The matching project image rule error or the project did not generate an image')#没有找到需要打包的镜像
    #tag = get_git_head()
    for num,i in enumerate(images_list[:-1]):
        tmp = i.split(":")
        image_id = tmp[0]
        image_name = ":".join([tmp[1],tag])
        update_dcoker_name ="docker tag %s %s"%(image_id,image_name) #重新修改镜像的标签信息
        print (update_dcoker_name)
        run_cmd(update_dcoker_name)#修改项目产生的镜像名称
        save_dockers = "docker save -o %s/%s/%s.tar %s" % (
        GENERATE_IMAGE_PATH, project_name, image_name.replace("/", "-"),image_name)  # 打包镜像
        #print (save_dockers)
        run_cmd(save_dockers)#将镜像打包
        remove_images = "docker rmi %s -f"%(image_name)#删除镜像
        #remove_images = "docker rmi %s -f" %(image_id)
        #run_cmd(remove_images)

def check_baseimage_version(baseimage_name,project_name,setting_name):#负责检查基础镜像信息，不存在则创建，配置更新则更新镜像
    """
    :param image_name:  基础镜像名字
    :param project_name: 项目名称
    :param setting_name: 需要检查的配置文件
    :return:
    """

    ret = build_base_image(baseimage_name,project_name,setting_name)
    if ret:#存在镜像
        isUpdate = update_base_image(baseimage_name,project_name,setting_name)#检查镜像是否需要更新
        if isUpdate:#更新镜像
            raise RuntimeError('update_base_image')
    else:#不存在镜像，已经建立好镜像，主动抛出异常
        raise RuntimeError('build_base_image')

def transfer_ssh_file(project_name,project_images_filter,upload_flag,ip,usr,passwd,image_registry,yam_name):
    ssh = SSHManager(ip, usr, passwd)
    regis_ip,_=image_registry.split(":")
    ssh_docker_registry = SSHManager(regis_ip, usr, passwd)
    docker_matching_image = """docker rmi $(docker images | grep "none" | awk '{print $3}')"""#删除none镜像
    ssh.ssh_exec_cmd(docker_matching_image)
    ssh.ssh_exec_cmd("mkdir %s/%s"%(MASTER_SAVE_PATH,project_name))
    ssh_docker_registry.ssh_exec_cmd(docker_matching_image)
    ssh_docker_registry.ssh_exec_cmd("mkdir %s/%s"%(MASTER_SAVE_PATH,project_name))
    dirs = os.listdir("%s/%s"%(GENERATE_IMAGE_PATH,project_name))
    docker_matching_image = """docker images --format "{{.ID}}:{{.Repository}}:{{.Tag}}" |grep -w %s""" % (
        project_images_filter)
    docker_images = run_cmd(docker_matching_image)
    images_list = docker_images.split("\n")
    for file_name in dirs:
        print (file_name)
        if os.path.splitext(file_name)[1] == '.tar':
            tmp1 = '%s/%s/%s'%(GENERATE_IMAGE_PATH,project_name,file_name)
            tmp2 = '%s/%s/%s'%(MASTER_SAVE_PATH,project_name,file_name)
            if upload_flag == "false" or upload_flag == "all":  # 只传输压缩文件
                ssh.ssh_exec_shell(tmp1,tmp2)
                ssh.ssh_exec_cmd("docker load -i %s/%s/%s" % (MASTER_SAVE_PATH, project_name, file_name))

            if upload_flag == "true" or upload_flag == "all":  # 上传镜像仓库
                ssh_docker_registry.ssh_exec_shell(tmp1,tmp2)#复制到镜像仓库
                ssh_docker_registry.ssh_exec_cmd("docker load -i %s/%s/%s" % (MASTER_SAVE_PATH, project_name, file_name))
    ssh.ssh_exec_cmd("rm -rf %s/%s/*.tar" % (MASTER_SAVE_PATH, project_name))
    ssh_docker_registry.ssh_exec_cmd("rm -rf %s/%s/*.tar" % (MASTER_SAVE_PATH, project_name))
    for num, i in enumerate(images_list[:-1]):
        tmp = i.split(":")
        image_id = tmp[0]
        if upload_flag == "true" or upload_flag == "all":  # 上传镜像仓库
            image_name = ":".join([tmp[1], tag])
            update_tag = "docker tag %s  %s/%s"%(image_name, image_registry, image_name)
            ssh_docker_registry.ssh_exec_cmd(update_tag)
            upload_images = "docker push %s/%s" % (image_registry, image_name)  # 上传镜像仓库
            ssh_docker_registry.ssh_exec_cmd(upload_images)
            ssh_docker_registry.ssh_exec_cmd("docker rmi %s"%(image_name))
            ssh_docker_registry.ssh_exec_cmd("docker rmi %s/%s" % (image_registry,image_name))
        print ("delete  %s"%(image_id))
        remove_images = "docker rmi %s -f" % (image_id)  # 删除镜像
        run_cmd(remove_images)
    #ssh.ssh_exec_shell(yam_name, "%s/%s" % (MASTER_SAVE_PATH, yam_name))
    ssh.ssh_exec_cmd("kubectl delete -f %s/%s" % (MASTER_SAVE_PATH, yam_name))
    ssh.ssh_exec_cmd("kubectl create -f %s/%s" % (MASTER_SAVE_PATH, yam_name))

def main():
    """
    choose: check
    arg[2] :baseimage_name  基础镜像名称
    arg[3] :project_name   项目名称
    arg[4] :setting_name    检查的配置文件

    choose: save
    arg[2] :save_images_filter 需要打包的镜像规则
    :return:
    """
    #检查Dockerfile Update_Dockerfile 是否存在

    choose = sys.argv[1]
    if choose == "check":
        print ("check")
        if len(sys.argv) <5:
            raise RuntimeError('built_image.py check Parameter is not complete!!!!!')
        baseimage_name = sys.argv[2]
        project_name = sys.argv[3]
        setting_name = sys.argv[4]
        check_baseimage_version(baseimage_name,project_name,setting_name)
    elif choose == "save":
        print ("save")
        project_name = sys.argv[2]
        project_images_filter = sys.argv[3].strip()
        upload_flag = sys.argv[4].strip()
        print(upload_flag)

        """
        if upload_flag != "false" or upload_flag != "true" or upload_flag != "all":
            raise RuntimeError('built_image.py save  UPLOAD_IMAGE_REP Parameter is wrong !!!!!')
        if upload_flag == "true":
            print ("No packaging is required for the upload repository")
            return
        """
        print (project_images_filter)
        save_images_file(project_name,project_images_filter)
    elif choose == "upload":
        print("upload")
        project_name = sys.argv[2]
        project_images_filter = sys.argv[3].strip()
        upload_flag = sys.argv[4].strip()
        target_IP= sys.argv[5].strip()
        target_USER = sys.argv[6].strip()
        target_PASSWD = sys.argv[7].strip()
        image_registry = sys.argv[8].strip()
        yam_name = sys.argv[9].strip()
        print(upload_flag)
        transfer_ssh_file(project_name,project_images_filter,upload_flag,target_IP,target_USER,target_PASSWD,image_registry,yam_name)

    elif choose == "jump":
        print ("jump")
    else:
        raise RuntimeError('Parameter error!!!!')



if __name__ == "__main__":
    main()





