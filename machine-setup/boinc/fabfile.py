"""
Fabric to be run on the BOINC server to configure things
"""
from fabric.decorators import task, parallel, serial, roles

PROJECT_NAME="pogs"
PROJECT_ROOT="/home/ec2-user/projects/#{PROJECT_NAME}"
APP_NAME="magphys_wrapper"
APP_VERSION=1
PLATFORMS=["windows_x86_64", "windows_intelx86", "x86_64-apple-darwin", "x86_64-pc-linux-gnu", "i686-pc-linux-gnu"]
PLATFORM_DIR = "#{PROJECT_ROOT}/apps/#{APP_NAME}/#{APP_VERSION}"
BOINC_TOOLS_DIR="/home/ec2-user/boinc/tools"
SOURCE_DIR="/home/ec2-user/boinc-magphys"

desc 'setup project website'
task :setup_website do
sh "cp #{PROJECT_ROOT}/#{PROJECT_NAME}.httpd.conf /etc/httpd/conf.d"
sh "/etc/init.d/httpd restart"
end

desc 'copy to apps/platform directory'
task :copy_files do
cp_r "#{SOURCE_DIR}/server/config/templates", "#{PROJECT_ROOT}"

PLATFORMS.each { |platform|
               mkdir_p "#{PLATFORM_DIR}/#{platform}"
cp FileList["#{SOURCE_DIR}/client/platforms/#{platform}/*"], "#{PLATFORM_DIR}/#{platform}", :preserve => true
cp FileList["#{SOURCE_DIR}/client/platforms/common/*"], "#{PLATFORM_DIR}/#{platform}", :preserve => true
}

cp "#{SOURCE_DIR}/server/config/project.xml", "#{PROJECT_ROOT}", :preserve => true

# Now added
sh "#{PROJECT_ROOT}/bin/xadd"
end

desc 'sign files'
task :sign_files => :copy_files do
PLATFORMS.each { |platform|
    FileList["#{PLATFORM_DIR}/#{platform}/*"].exclude("#{PLATFORM_DIR}/#{platform}/version.xml", "#{PLATFORM_DIR}/#{platform}/*.sig").to_a().each { |f|
            sh "#{BOINC_TOOLS_DIR}/sign_executable #{f} #{PROJECT_ROOT}/keys/code_sign_private | tee #{f}.sig"
}
}
end

desc 'update versions'
task :update_versions => :sign_files do
sh "cd #{PROJECT_ROOT}; yes | #{PROJECT_ROOT}/bin/update_versions"
sh "cd #{PROJECT_ROOT}; #{PROJECT_ROOT}/bin/xadd"
end

desc 'starts the BOINC daemons'
task :start_daemons do
sh "cd #{PROJECT_ROOT}; #{PROJECT_ROOT}/bin/start"
end

@task
def start_daemons:
    with cd('')
