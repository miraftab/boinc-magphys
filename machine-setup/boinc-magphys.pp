package { 'httpd':
    ensure => installed,
}
package { 'autoconf':
    ensure => installed,
}
package { 'automake':
    ensure => installed,
}
package { 'binutils':
    ensure => installed,
}
package { 'gcc':
    ensure => installed,
}
package { 'gcc-c++':
    ensure => installed,
}
package { 'gdb':
    ensure => installed,
}
package { 'libtool':
    ensure => installed,
}
package { 'make':
    ensure => installed,
}
package { 'gcc-gfortran':
    ensure => installed,
}
package { 'openssl':
    ensure => installed,
}
package { 'openssl-devel':
    ensure => installed,
}
package { 'mysql-devel':
    ensure => installed,
}
package { 'php':
    ensure => installed,
}
package { 'php-cli':
    ensure => installed,
}
package { 'php-gd':
    ensure => installed,
}
package { 'php-mysql':
    ensure => installed,
}
package { 'python-devel':
    ensure => installed,
}
package { 'python27':
    ensure => installed,
}
package { 'python27-devel':
    ensure => installed,
}
package { 'MySQL-python':
    ensure => installed,
}
package { 'subversion':
    ensure => installed,
}
package { 'rubygem-rake':
    ensure => installed,
}

# We have to install the MySQL - even though we don't necessarily need to activate - BOINC gets stroppy
package { 'mysql-server':
    ensure => installed,
}

user { 'apache':
  ensure  => present,
  groups => ['ec2-user'],
  require => User['ec2-user'],
}

service { 'httpd':
    ensure => running,
    enable => true,
    require => Package['httpd']
}

file { "/home/ec2-user/galaxies":
    ensure => "directory",
    owner  => "ec2-user",
    mode   => 775,
    require => User['ec2-user'],
}

file { "/home/ec2-user/f2wu":
    ensure => "directory",
    owner  => "ec2-user",
    mode   => 775,
    require => User['ec2-user'],
}

file { "/home/ec2-user/boinc":
    ensure => "directory",
    owner  => "ec2-user",
    mode   => 775,
    require => User['ec2-user'],
}
