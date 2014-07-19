


userid()
{
	id | sed 's/^uid=\([0-9]\{1,\}\)([^)]*).*$/\1/g'
	return "${?}"
}

username()
{
	id | sed 's/^uid=[0-9]\{1,\}(\([^)]*\)).*$/\1/g'
	return "${?}"
}

utils_log()
{
	local utils_log_RC
	if type "${UTILS_LOG}" 1>/dev/null 2>&1
	then
		"${UTILS_LOG}" "${@}"
		utils_log_RC="${?}"
		return "${utils_log_RC}"
	fi
	return 0;
}

utils_log_fork()
{
	local utils_log_fork_RC
	if type "${UTILS_LOG_FORK}" 1>/dev/null 2>&1
	then
		"${UTILS_LOG_FORK}" "${@}"
		utils_log_fork_RC="${?}"
	else
		"${@}"
		utils_log_fork_RC="${?}"
	fi
	return "${utils_log_fork_RC}"
}

verbose()
{
	if [ -n "${VERBOSE}" ]
	then
		return 0;
	fi
	return 1;
}

zassign()
{
	local VAR="${1}"
	local VALUE="${2}"
	if [ -z "${!VAR}" ]
	then
		eval ${VAR}="${VALUE}"
		return "${?}"
	fi
	return "0"
}

zassign UTILS_EXIT "exit"

eecho()
{
	echo "${@}" 1>&2
	utils_log "ERROR" "${@}"
	return "${?}"
}

assert()
{
	iassert "${BASH_SOURCE[1]}:${FUNCNAME[1]}:${BASH_LINENO[0]}" "${@}"
	local assert_RC="${?}"
	test "${assert_RC}" != "0" && exit "${assert_RC}";
	return 0;
}

assert_xs()
{
	iassert_xs "${BASH_SOURCE[1]}:${FUNCNAME[1]}:${BASH_LINENO[0]}" "${@}"
	local assert_xs_RC="${?}"
	test "${assert_xs_RC}" != "0" && exit "${assert_xs_RC}";
	return 0;
}

assert_command()
{
	iassert_command "${BASH_SOURCE[1]}:${FUNCNAME[1]}:${BASH_LINENO[0]}" "${@}"
	local assert_command_RC="${?}"
	test "${assert_command_RC}" != "0" && exit "${assert_command_RC}";
	return 0;
}

rassert()
{
	iassert "${BASH_SOURCE[1]}:${FUNCNAME[1]}:${BASH_LINENO[0]}" "${@}"
	local rassert_RC="${?}"
	return "${rassert_RC}";
	return 0;
}

rassert_command()
{
	iassert_command "${BASH_SOURCE[1]}:${FUNCNAME[1]}:${BASH_LINENO[0]}" "${@}"
	local rassert_command_RC="${?}"
	return "${rassert_command_RC}";
	return 0;
}

rassert_xs()
{
	iassert_xs "${BASH_SOURCE[1]}:${FUNCNAME[1]}:${BASH_LINENO[0]}" "${@}"
	local rassert_xs_RC="${?}"
	return "${rassert_xs_RC}";
	return 0;
}

iassert()
{
	local iassert_command_POSITION iassert_command_EXPRESSION iassert_command_MESSAGE
	iassert_command_POSITION="${1}"
	iassert_command_EXPRESSION="${2}"
	iassert_command_MESSAGE="${3}"
	shift 3;
	eval test ${iassert_command_EXPRESSION}
	local iassert_RC="${?}"
	#echo "${1} ${2} ${3} : ${iassert_RC}"
	if [ "${iassert_RC}" != "0" ]
	then
		if [ -n "${VERBOSE}" -o -z "${iassert_command_MESSAGE}" ]
		then
			eecho "Assertion failed: ${iassert_command_EXPRESSION} "`eval echo -n "\(" ${iassert_command_EXPRESSION} "\)" `"" "[${iassert_command_POSITION}]"
		fi
		if [ -n "${iassert_command_MESSAGE}" ]
		then
			eecho "ERROR: ${iassert_command_MESSAGE} [${iassert_command_POSITION}]" 
		fi
		return 1;
	fi
	return 0;
}

iassert_command()
{
	local iassert_command_POSITION iassert_command_COMMAND iassert_command_MESSAGE
	iassert_command_POSITION="${1}"
	iassert_command_COMMAND="${2}"
	iassert_command_MESSAGE="${3}"
	shift 3;
	type "${iassert_command_COMMAND}" 1>/dev/null 2>&1
	local iassert_command_RC="${?}"
	if [ "${iassert_command_RC}" != "0" ]
	then
		if [ -n "${VERBOSE}" -o -z "${iassert_command_MESSAGE}" ]
		then
			eecho "Assertion failed: command ${iassert_command_COMMAND} not found" "${@}" "[${iassert_command_POSITION}]"
		fi
		if [ -n "${iassert_command_MESSAGE}" ]
		then
			eecho "ERROR: ${iassert_command_MESSAGE} [${iassert_command_POSITION}]"
		fi
		return 1;
	fi
	return 0;
}

iassert_xs()
{
	local iassert_xs_POSITION iassert_xs_XS iassert_xs_MESSAGE
	iassert_xs_POSITION="${1}"
	iassert_xs_XS="${2}"
	iassert_xs_MESSAGE="${3}"
	shift 3;
	utils_log_fork "${@}"
	local iassert_xs_RC="${?}"
	if [ "${iassert_xs_RC}" != "${iassert_xs_XS}" ]
	then
		if [ -n "${VERBOSE}" -o -z "${iassert_xs_MESSAGE}" ]
		then
			eecho "Assertion failed: [${iassert_xs_POSITION}] [(xs=${iassert_xs_RC}) != ${iassert_xs_XS}] ${@}"
			utils_log "FAULT" "Assertion failed: [${iassert_xs_POSITION}] [(xs=${iassert_xs_RC}) != ${iassert_xs_XS}] ${@}"
		fi
		if [ -n "${iassert_xs_MESSAGE}" ]
		then
			eecho "ERROR: ${iassert_xs_MESSAGE} [${iassert_xs_POSITION}]"

		fi
		return 1;
	fi
	return 0;
}

qshow_vars()
{
	local VAR
	for VAR in "${@}"
	do
		printf "${VAR}=[\"%q\"]\n" ${!VAR}
	done
	return 0;
}

show_vars()
{
	local VAR
	for VAR in "${@}"
	do
		eecho "${VAR}=[${!VAR}]"
	done
	return 0;
}

# who called ?
# ${BASH_SOURCE[1]}:${FUNCNAME[1]}:${BASH_LINENO[0]}

debug_vars()
{
	if [ -n "${VERBOSE}" ]
	then
		local VAR
		for VAR in "${@}"
		do
			eecho "`create_tabs ${#BASH_LINENO[@]}`""${VAR}=[${!VAR}]" "[${BASH_SOURCE[1]}:${FUNCNAME[1]}:${BASH_LINENO[0]}]"
		done
	fi
	utils_log "DEBUG" "`create_tabs ${#BASH_LINENO[@]}`""${VAR}=[${!VAR}]" "[${BASH_SOURCE[1]}:${FUNCNAME[1]}:${BASH_LINENO[0]}]"
}

show_version()
{
	echo "@CS_COMP_TYPE@-@CS_COMP_NAME@-@CS_COMP_VERSION@ : $1"
}

create_tabs()
{
	local COUNTER=${1}
	while (( COUNTER > 0 ))
	do
		echo -n "  "
		(( COUNTER-- ))
	done
}

decho()
{
	if [ -n "${VERBOSE}" ]
	then
		eecho "`create_tabs ${#BASH_LINENO[@]}`""${BASH_SOURCE[1]}:${FUNCNAME[1]}:${BASH_LINENO[0]}:${@}"
	fi
	utils_log "DEBUG" "${@}"
}

dentry()
{
	if [ -n "${VERBOSE}" ]
	then
		eecho "`create_tabs ${#BASH_LINENO[@]}`""${BASH_SOURCE[2]}:${FUNCNAME[2]}:${BASH_LINENO[1]}  -> ${BASH_SOURCE[1]}:${FUNCNAME[1]}:${BASH_LINENO[0]}:entry:${@}"
	fi
	utils_log "DEBUG" "`create_tabs ${#BASH_LINENO[@]}`""${BASH_SOURCE[2]}:${FUNCNAME[2]}:${BASH_LINENO[1]}  -> ${BASH_SOURCE[1]}:${FUNCNAME[1]}:${BASH_LINENO[0]}:entry:${@}"
}

dfork()
{
	if [ -n "${VERBOSE}" ]
	then
		eecho "`create_tabs ${#BASH_LINENO[@]}`""${BASH_SOURCE[1]}:${FUNCNAME[1]}:${BASH_LINENO[0]}:${@}"
	fi
	utils_log_fork "${@}"
	return "${?}"
}

drfork()
{
	if [ -n "${VERBOSE}" ]
	then
		eecho "`create_tabs ${#BASH_LINENO[@]}`""${BASH_SOURCE[1]}:${FUNCNAME[1]}:${BASH_LINENO[0]}:entry: ${@}"
	fi
	utils_log_fork "${@}"
	local drfork_RC="${?}"
	if [ -n "${VERBOSE}" ]
	then
		eecho "`create_tabs ${#BASH_LINENO[@]}`""${BASH_SOURCE[1]}:${FUNCNAME[1]}:${BASH_LINENO[0]}:return: ${@} : RC=${drfork_RC}"
	fi
	return "${drfork_RC}"
}

