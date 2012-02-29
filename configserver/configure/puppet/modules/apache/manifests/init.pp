import "configserver"

class apache {
  class variables {
    $httpd_log_level = $httpd_log_level ? {
      ''        => 'debug',
      default   => $httpd_log_level
    }
    $config_server_context = $config_server_context ? {
      ''        => '',
      default   => $config_server_context
    }
    $config_server_url = $config_server_url ? {
      ''        => 'http://localhost:4567/',
      default   => $config_server_url
    }
    $proxy_type = $proxy_type ? {
      ''        => 'apache',
      default   => $proxy_type
    }
  }

  class base {
    package { "apache":
      name => "httpd",
      ensure => installed,
    }

    exec { "permit-http-networking":
      command   => "/usr/sbin/setsebool -P httpd_can_network_connect 1",
      logoutput => true,
      unless    => "/usr/bin/test 'Disabled' = `/usr/sbin/getenforce`",
      require   => Package["apache"],
      notify    => Exec["graceful-apache"],
    }

    exec { "graceful-apache":
      command => "/sbin/service httpd graceful",
      refreshonly => true,
      require => Package["apache"],
    }
  }

  define proxy ( $drop_file_dir = 'cs443') {
    $apache_path      = "/etc/httpd"
    $apache_conf_path = "${apache_path}/conf.d"
    $drop_file_path   = "${apache_conf_path}/${drop_file_dir}"

    $drop_file = "${drop_file_path}/config_server_proxy.conf"

    file { $drop_file:
      ensure  => $ensure,
      content => template("apache/proxy.erb"),
      notify  => Exec["graceful-apache"],
      require => Package["apache"],
    }
  }

  class conductor::ssl {
    $drop_file_dir = "aeolus-conductor.d"
    # Make sure the aeolus-conductor.d drop file directory is available
    file { 'vhost-443-addl':
      name => "/etc/httpd/conf.d/${drop_file_dir}",
      ensure => directory,
      mode => 0644, owner => root, group => root,
      require => Package["apache"],
      notify  => Exec["graceful-apache"]
    }

    proxy { "configserver_proxy": drop_file_dir => "$drop_file_dir" }
  }

  class ssl {
    include apache::variables

    $pk_file="/etc/pki/tls/private/config-server.key"
    $cert_file="/etc/pki/tls/config-server.crt"
    package { ["openssl", "openssh"]:
      ensure => installed,
    }

    package { "mod_ssl":
      ensure => installed,
      require => Package["apache"],
      notify => Exec["graceful-apache"],
    }

    exec { "pk-file":
      command => "/usr/sbin/selinuxenabled && /usr/bin/runcon -t unconfined_t /usr/bin/ssh-keygen -t rsa -f ${pk_file} -N ''",
      creates => "$pk_file",
      require => Package["mod_ssl"],
      notify => Exec["graceful-apache"],
    }

    exec { "sign-request":
      command => "/usr/bin/openssl req -batch -new -key ${pk_file} -out /etc/pki/tls/config-server.csr",
      creates => "/etc/pki/tls/config-server.csr",
      require => Exec["pk-file"],
    }

    exec { "cert":
      command => "/usr/bin/openssl x509 -req -days 365 -in /etc/pki/tls/config-server.csr -signkey ${pk_file} -out ${cert_file}",
      creates => "$cert_file",
      require => Exec["sign-request"],
      notify => Exec["graceful-apache"],
    }

    file { "vhost-443":
      name => "/etc/httpd/conf.d/aeolus-configserver-vhost443.conf",
      mode => 0644, owner => root, group => root,
      ensure => present,
      content => template("apache/vhost443.erb"),
      require => Package["mod_ssl"],
      notify => Exec["graceful-apache"],
    }

    $drop_file_dir = "cs443"
    # The aeolus-configserver-vhost443.conf file allows for additional configs
    # for the vhost to be placed in the following directory
    file { 'vhost-443-addl':
      name => "/etc/httpd/conf.d/${drop_file_dir}",
      ensure => directory,
      mode => 0644, owner => root, group => root,
      require => Package["apache"],
      notify  => Exec["graceful-apache"]
    }

    proxy { "configserver_proxy": drop_file_dir => "$drop_file_dir" }

    exec { "config-iptables-for-443":
      command   => "/sbin/iptables -I INPUT -m state --state NEW -m tcp -p tcp --dport 443 -j ACCEPT",
      logoutput => true,
      onlyif    => "/usr/bin/test `iptables -L | /bin/grep -E 'ACCEPT .* tcp .*(https|443)' | /usr/bin/wc -l` -eq 0",
      require => Package["apache"],
      notify  => Exec["graceful-apache"]
    }

    exec { "config-iptables-save":
      command   => "/usr/bin/test -x /usr/libexec/iptables.init && /usr/libexec/iptables.init save || /sbin/service iptables save",
      logoutput => true,
      onlyif    => "/usr/bin/test `/bin/grep -E 'dport (https|443)' /etc/sysconfig/iptables | /usr/bin/wc -l` -eq 0",
      require => [Package["apache"], Exec["config-iptables-for-443"]],
      notify  => Exec["graceful-apache"]
    }
  }

  class vhost80 {
    file { 'vhost-80':
      name => "/etc/httpd/conf.d/aeolus-configserver-vhost80.conf",
      mode => 0644, owner => root, group => root,
      ensure => present,
      content => template("apache/vhost80.erb"),
      require => Package["apache"],
      notify => Exec["graceful-apache"],
    }

    # The aeolus-configserver-vhost80.conf file allows for additional configs
    # for the vhost to be placed in the following directory
    file { 'vhost-80-addl':
      name => "/etc/httpd/conf.d/cs80",
      ensure => directory,
      mode => 0644, owner => root, group => root,
      require => Package["apache"],
      notify => Exec["graceful-apache"]
    }
  }
}
